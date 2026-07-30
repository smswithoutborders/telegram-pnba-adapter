# SPDX-License-Identifier: GPL-3.0-only

import base64
from typing import Any, Dict, Optional

from telethon.errors import SessionPasswordNeededError

from config import load_credentials
from logutils import get_logger
from protocol_interfaces import PNBAProtocolInterface
from telegram_client import (
    Attachment,
    client_session,
    should_force_document,
    to_telegram_file,
)
from utils import require

logger = get_logger(__name__)


class TelegramPNBAAdapter(PNBAProtocolInterface):
    """Adapter for integrating TelegramClient with the PNBA protocol."""

    def __init__(self):
        self.credentials = load_credentials(self.config)

    async def send_authorization_code(
        self, phone_number: str, **kwargs
    ) -> Dict[str, Any]:
        base_path = kwargs.get("base_path", None)
        async with client_session(
            self.credentials, phone_number, base_path, overwrite=True
        ) as (client, registry):
            if await client.is_user_authorized():
                logger.warning("User already authorized.")
                return {"success": False, "message": "User already authorized."}

            result = await client.send_code_request(phone=phone_number)
            registry.update(phone_code_hash=result.phone_code_hash)

            logger.info("Authorization code sent.")
            return {"success": True, "message": "Authorization code sent."}

    async def validate_code_and_fetch_user_info(
        self, phone_number: str, code: str, **kwargs
    ) -> Dict[str, Any]:
        base_path = kwargs.get("base_path", None)
        async with client_session(self.credentials, phone_number, base_path) as (
            client,
            registry,
        ):
            phone_code_hash = registry.read().get("phone_code_hash")
            if not phone_code_hash:
                logger.warning("Missing phone_code_hash in registry.")

            try:
                await client.sign_in(
                    phone=phone_number, phone_code_hash=phone_code_hash, code=code
                )
                user = await client.get_me()
                registry.clear()

                logger.info("User authorized successfully.")
                return {
                    "two_step_verification_enabled": False,
                    "userinfo": {
                        "account_identifier": phone_number,
                        "name": user.first_name,
                    },
                }
            except SessionPasswordNeededError:
                logger.info("Two-step verification is enabled.")
                return {
                    "two_step_verification_enabled": True,
                    "userinfo": {
                        "account_identifier": phone_number,
                        "name": None,
                    },
                }

    async def validate_password_and_fetch_user_info(
        self, phone_number: str, password: str, **kwargs
    ) -> Dict[str, Any]:
        base_path = kwargs.get("base_path", None)
        async with client_session(self.credentials, phone_number, base_path) as (
            client,
            registry,
        ):
            await client.sign_in(password=password)
            user = await client.get_me()
            registry.clear()

            logger.info("Password validation successful.")
            return {
                "userinfo": {
                    "account_identifier": phone_number,
                    "name": user.first_name,
                },
            }

    async def invalidate_session(self, phone_number: str, **kwargs) -> bool:
        base_path = kwargs.get("base_path", None)
        async with client_session(self.credentials, phone_number, base_path) as (
            client,
            registry,
        ):
            await client.log_out()
            registry.invalidate()

            logger.info("Session invalidated.")
            return True

    async def send_message(self, phone_number: Optional[str] = None, **kwargs) -> bool:
        if not phone_number:
            raise ValueError(
                "Telegram requires a bound session: 'phone_number' is required."
            )
        (recipient, message) = require(kwargs, "recipient", "message")
        base_path = kwargs.get("base_path", None)

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
                raise ValueError(f"Invalid attachment data in '{filename}'.") from exc

        async with client_session(self.credentials, phone_number, base_path) as (
            client,
            _,
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

            logger.info("Message sent to %s", recipient)
            return True
