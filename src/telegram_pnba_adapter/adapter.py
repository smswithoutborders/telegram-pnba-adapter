# SPDX-License-Identifier: GPL-3.0-only

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import override

from relaysms_adapter_sdk import (
    Account,
    AuthenticationError,
    CodeRequest,
    CodeSent,
    CodeVerificationRequest,
    InvalidParamsError,
    PasswordRequired,
    PasswordVerificationRequest,
    PNBAAdapter,
    RateLimitedError,
    RevokeRequest,
    SendRequest,
    SendResult,
    TokenInvalidError,
    UpstreamError,
)
from telethon import errors

from telegram_pnba_adapter import credentials
from telegram_pnba_adapter.pending_auth_store import PendingAuthStore
from telegram_pnba_adapter.telegram_client import (
    client_session,
    should_force_document,
    to_telegram_file,
)

logger = logging.getLogger(__name__)

REJECTED_LOGIN = (
    errors.PhoneCodeInvalidError,
    errors.PhoneCodeExpiredError,
    errors.PasswordHashInvalidError,
)
INVALID_SESSION = (errors.UnauthorizedError, errors.AuthKeyError)


class TelegramAdapter(PNBAAdapter):
    def __init__(self) -> None:
        self.credentials = credentials.load()

    @override
    async def send_code(self, request: CodeRequest) -> CodeSent:
        async with (
            _telegram_errors(),
            client_session(self.credentials) as (client, snapshot),
        ):
            result = await client.send_code_request(phone=request.phone_number)
        with self._pending() as store:
            store.set(
                request.phone_number, result.phone_code_hash, snapshot.session_string
            )
        return CodeSent(message="Authorization code sent.")

    @override
    async def verify_code(
        self, request: CodeVerificationRequest
    ) -> Account | PasswordRequired:
        with self._pending() as store:
            pending = store.get(request.phone_number)
            if not pending:
                raise AuthenticationError("Request a new code for this number.")
            async with (
                _telegram_errors(),
                client_session(self.credentials, pending.session_string) as (
                    client,
                    snapshot,
                ),
            ):
                try:
                    await client.sign_in(
                        phone=request.phone_number,
                        phone_code_hash=pending.phone_code_hash,
                        code=request.code,
                    )
                    user = await client.get_me()
                except errors.SessionPasswordNeededError:
                    user = None
            if user is None:
                store.set(
                    request.phone_number,
                    pending.phone_code_hash,
                    snapshot.session_string,
                )
                return PasswordRequired()
            store.clear(request.phone_number)
        return _account(request.phone_number, user, snapshot.session_string)

    @override
    async def verify_password(self, request: PasswordVerificationRequest) -> Account:
        with self._pending() as store:
            pending = store.get(request.phone_number)
            if not pending:
                raise AuthenticationError("Verify the code for this number first.")
            async with (
                _telegram_errors(),
                client_session(self.credentials, pending.session_string) as (
                    client,
                    snapshot,
                ),
            ):
                await client.sign_in(password=request.password)
                user = await client.get_me()
            store.clear(request.phone_number)
        return _account(request.phone_number, user, snapshot.session_string)

    @override
    async def send_message(self, request: SendRequest) -> SendResult:
        account = request.account
        if account is None or not (account.token or {}).get("session_string"):
            raise InvalidParamsError("Telegram sends only from a linked account.")
        message = request.message
        if not message.recipient:
            raise InvalidParamsError("A recipient is required.")

        session_string = account.token["session_string"]
        async with (
            _telegram_errors(),
            client_session(self.credentials, session_string) as (client, snapshot),
        ):
            if message.attachments:
                files = [to_telegram_file(a) for a in message.attachments]
                await client.send_file(
                    message.recipient,
                    files if len(files) > 1 else files[0],
                    caption=message.body,
                    force_document=should_force_document(message.attachments),
                )
            else:
                await client.send_message(message.recipient, message.body)
        logger.info("Message sent.")

        if snapshot.session_string and snapshot.session_string != session_string:
            return SendResult(token={"session_string": snapshot.session_string})
        return SendResult()

    @override
    async def revoke(self, request: RevokeRequest) -> None:
        session_string = (request.account.token or {}).get("session_string")
        if session_string:
            async with client_session(self.credentials, session_string) as (client, _):
                try:
                    await client.log_out()
                except INVALID_SESSION as e:
                    logger.info("Session was already invalid: %s", e)
        with self._pending() as store:
            store.clear(request.account.identifier)

    def _pending(self) -> PendingAuthStore:
        return PendingAuthStore(self.credentials.api_hash)


def _account(phone_number: str, user, session_string: str | None) -> Account:
    return Account(
        identifier=phone_number,
        name=user.first_name,
        token={"session_string": session_string},
    )


@asynccontextmanager
async def _telegram_errors() -> AsyncIterator[None]:
    """Map Telegram failures to AdapterErrors."""
    try:
        yield
    except REJECTED_LOGIN as e:
        raise AuthenticationError(str(e)) from e
    except INVALID_SESSION as e:
        raise TokenInvalidError(f"The Telegram session is no longer valid: {e}") from e
    except errors.FloodWaitError as e:
        raise RateLimitedError(str(e), retry_after=e.seconds) from e
    except (errors.PhoneNumberInvalidError, errors.UsernameInvalidError) as e:
        raise InvalidParamsError(str(e)) from e
    except (errors.RPCError, ConnectionError, OSError) as e:
        raise UpstreamError(f"Telegram failed: {e}") from e
