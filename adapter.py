# SPDX-License-Identifier: GPL-3.0-only

import base64
from typing import Any, Dict, Optional

from telethon import errors
from telethon.errors import SessionPasswordNeededError

from config import load_credentials
from logutils import get_logger
from pending_auth_store import PendingAuthStore
from protocol_interfaces import PNBAProtocolInterface
from telegram_client import (
    Attachment,
    client_session,
    should_force_document,
    to_telegram_file,
)
from utils import require

logger = get_logger(__name__)


class SessionInvalidError(RuntimeError):
    """Raised when a Telegram session is no longer valid and needs re-authentication."""


class TelegramPNBAAdapter(PNBAProtocolInterface):
    """Adapter for integrating TelegramClient with the PNBA protocol."""

    def __init__(self):
        self.credentials = load_credentials(self.config)

    async def send_authorization_code(
        self, phone_number: str, **kwargs
    ) -> Dict[str, Any]:
        base_path = kwargs.get("base_path")

        async with client_session(self.credentials) as (client, snapshot):
            result = await client.send_code_request(phone=phone_number)

        with PendingAuthStore(self.credentials, base_path) as store:
            store.set(phone_number, result.phone_code_hash, snapshot.session_string)

        logger.info("Authorization code sent.")
        return {"success": True, "message": "Authorization code sent."}

    async def validate_code_and_fetch_user_info(
        self, phone_number: str, code: str, **kwargs
    ) -> Dict[str, Any]:
        base_path = kwargs.get("base_path")

        two_step_verification_enabled = False
        name = None

        with PendingAuthStore(self.credentials, base_path) as store:
            pending = store.get(phone_number)
            if not pending:
                logger.error(
                    "No pending authorization found for this phone number; "
                    "call send_authorization_code first."
                )
                raise ValueError(
                    "No pending authorization found for this phone number."
                )

            async with client_session(self.credentials, pending.session_string) as (
                client,
                snapshot,
            ):
                try:
                    await client.sign_in(
                        phone=phone_number,
                        phone_code_hash=pending.phone_code_hash,
                        code=code,
                    )
                    user = await client.get_me()
                    name = user.first_name
                except SessionPasswordNeededError:
                    logger.info("Two-step verification is enabled.")
                    two_step_verification_enabled = True

            if two_step_verification_enabled:
                store.set(
                    phone_number, pending.phone_code_hash, snapshot.session_string
                )
            else:
                store.clear(phone_number)
                logger.info("User authorized successfully.")

        result: Dict[str, Any] = {
            "two_step_verification_enabled": two_step_verification_enabled,
            "userinfo": {"account_identifier": phone_number, "name": name},
        }
        if not two_step_verification_enabled:
            result["session"] = {"session_string": snapshot.session_string}
        return result

    async def validate_password_and_fetch_user_info(
        self, phone_number: str, password: str, **kwargs
    ) -> Dict[str, Any]:
        base_path = kwargs.get("base_path")

        with PendingAuthStore(self.credentials, base_path) as store:
            pending = store.get(phone_number)
            if not pending:
                logger.error(
                    "No pending two-step verification found for this phone "
                    "number; call validate_code_and_fetch_user_info first."
                )
                raise ValueError(
                    "No pending two-step verification found for this phone number."
                )

            async with client_session(self.credentials, pending.session_string) as (
                client,
                snapshot,
            ):
                await client.sign_in(password=password)
                user = await client.get_me()

            store.clear(phone_number)

        logger.info("Password validation successful.")
        return {
            "userinfo": {
                "account_identifier": phone_number,
                "name": user.first_name,
            },
            "session": {"session_string": snapshot.session_string},
        }

    async def invalidate_session(self, phone_number: str, **kwargs) -> bool:
        (session,) = require(kwargs, "session")
        session_string = session["session_string"]

        async with client_session(self.credentials, session_string) as (client, _):
            try:
                await client.log_out()
            except (errors.UnauthorizedError, errors.AuthKeyError) as exc:
                logger.warning("Session already invalid server-side: %s", exc)

        base_path = kwargs.get("base_path")
        with PendingAuthStore(self.credentials, base_path) as store:
            store.clear(phone_number)

        logger.info("Session invalidated.")
        return True

    async def send_message(
        self, phone_number: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        if not phone_number:
            message = "Telegram requires a bound session: 'phone_number' is required."
            logger.error(message)
            raise ValueError(message)
        (session, recipient, message) = require(
            kwargs, "session", "recipient", "message"
        )
        session_string = session["session_string"]

        attachments = []
        for idx, att_dict in enumerate(kwargs.get("attachments") or []):
            filename = att_dict.get("filename", f"attachment_{idx}")
            try:
                attachments.append(
                    Attachment(
                        data=base64.b64decode(att_dict.get("data", "")),
                        filename=filename,
                        mimetype=att_dict.get("mimetype"),
                    )
                )
            except Exception as exc:
                message = f"Invalid attachment data in '{filename}'."
                logger.error(message)
                raise ValueError(message) from exc

        try:
            async with client_session(self.credentials, session_string) as (
                client,
                snapshot,
            ):
                if attachments:
                    files = [to_telegram_file(a) for a in attachments]
                    await client.send_file(
                        recipient,
                        files if len(files) > 1 else files[0],
                        caption=message,
                        force_document=should_force_document(attachments),
                    )
                else:
                    await client.send_message(recipient, message)
        except (errors.UnauthorizedError, errors.AuthKeyError) as exc:
            message = (
                f"Telegram session for {phone_number} is no longer valid and "
                f"requires re-authentication: {exc}"
            )
            logger.error(message)
            raise SessionInvalidError(message) from exc

        logger.info("Message sent to %s", recipient)

        result: Dict[str, Any] = {"success": True}
        if snapshot.session_string and snapshot.session_string != session_string:
            result["refreshed_session"] = {"session_string": snapshot.session_string}
        return result
