# SPDX-License-Identifier: GPL-3.0-only

import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from relaysms_adapter_sdk import (
    Account,
    Attachment,
    AuthenticationError,
    CodeRequest,
    CodeVerificationRequest,
    InvalidParamsError,
    Message,
    PasswordRequired,
    PasswordVerificationRequest,
    RateLimitedError,
    RevokeRequest,
    SendRequest,
    TokenInvalidError,
)
from relaysms_adapter_sdk.paths import CONFIG_DIR_ENV, STATE_DIR_ENV
from telethon import errors

from telegram_pnba_adapter import TelegramAdapter
from telegram_pnba_adapter import adapter as adapter_module
from telegram_pnba_adapter.telegram_client import SessionSnapshot

PHONE = "+237600000000"
# The token shape the adapter has always stored.
TOKEN = {"session_string": "s0"}


@pytest.fixture
def client(monkeypatch):
    client = AsyncMock()
    client.send_code_request.return_value = SimpleNamespace(phone_code_hash="h")
    client.get_me.return_value = SimpleNamespace(first_name="Ama")
    client.sessions = []

    @asynccontextmanager
    async def session(credentials, session_string=None):
        client.sessions.append(session_string)
        snapshot = SessionSnapshot()
        try:
            yield client, snapshot
        finally:
            snapshot.session_string = client.next_session

    client.next_session = "s1"
    monkeypatch.setattr(adapter_module, "client_session", session)
    return client


@pytest.fixture
def adapter(tmp_path, monkeypatch, client):
    monkeypatch.setenv(CONFIG_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(STATE_DIR_ENV, str(tmp_path / "state"))
    (tmp_path / "credentials.json").write_text(
        json.dumps({"api_id": "123", "api_hash": "hash"})
    )
    return TelegramAdapter()


def run(coroutine):
    return asyncio.run(coroutine)


def send(adapter, message, token=TOKEN):
    return run(adapter.send_message(SendRequest(message, Account(PHONE, token=token))))


class TestLink:
    def test_code(self, adapter, client):
        run(adapter.send_code(CodeRequest(PHONE)))
        account = run(adapter.verify_code(CodeVerificationRequest(PHONE, "12345")))
        assert account == Account(PHONE, token={"session_string": "s1"}, name="Ama")
        assert client.sessions == [None, "s1"]
        client.sign_in.assert_awaited_with(
            phone=PHONE, phone_code_hash="h", code="12345"
        )

    def test_two_step(self, adapter, client):
        client.sign_in.side_effect = [errors.SessionPasswordNeededError(None), None]
        run(adapter.send_code(CodeRequest(PHONE)))
        result = run(adapter.verify_code(CodeVerificationRequest(PHONE, "12345")))
        assert result == PasswordRequired()
        account = run(adapter.verify_password(PasswordVerificationRequest(PHONE, "pw")))
        assert account.token == {"session_string": "s1"}
        client.sign_in.assert_awaited_with(password="pw")

    def test_wrong_code(self, adapter, client):
        client.sign_in.side_effect = errors.PhoneCodeInvalidError(None)
        run(adapter.send_code(CodeRequest(PHONE)))
        with pytest.raises(AuthenticationError):
            run(adapter.verify_code(CodeVerificationRequest(PHONE, "0")))

    def test_no_code_requested(self, adapter):
        with pytest.raises(AuthenticationError, match="new code"):
            run(adapter.verify_code(CodeVerificationRequest(PHONE, "1")))


class TestSendMessage:
    def test_text_returns_changed_session(self, adapter, client):
        result = send(adapter, Message(body="hi", recipient="@friend"))
        client.send_message.assert_awaited_once_with("@friend", "hi")
        assert result.token == {"session_string": "s1"}
        assert client.sessions == ["s0"]

    def test_unchanged_session(self, adapter, client):
        client.next_session = "s0"
        assert send(adapter, Message(body="hi", recipient="@friend")).token is None

    def test_attachment_as_caption(self, adapter, client):
        photo = Attachment(b"img", "a.png", "image/png")
        send(adapter, Message(body="look", recipient="@f", attachments=(photo,)))
        kwargs = client.send_file.await_args.kwargs
        assert kwargs == {"caption": "look", "force_document": False}

    def test_needs_recipient(self, adapter):
        with pytest.raises(InvalidParamsError, match="recipient"):
            send(adapter, Message(body="hi"))

    def test_invalid_session(self, adapter, client):
        client.send_message.side_effect = errors.AuthKeyUnregisteredError(None)
        with pytest.raises(TokenInvalidError):
            send(adapter, Message(body="hi", recipient="@f"))

    def test_flood_wait(self, adapter, client):
        client.send_message.side_effect = errors.FloodWaitError(None, capture=30)
        with pytest.raises(RateLimitedError) as e:
            send(adapter, Message(body="hi", recipient="@f"))
        assert e.value.retry_after == 30


class TestRevoke:
    def test_logs_out(self, adapter, client):
        run(adapter.revoke(RevokeRequest(Account(PHONE, token=TOKEN))))
        client.log_out.assert_awaited_once()

    def test_already_invalid(self, adapter, client):
        client.log_out.side_effect = errors.AuthKeyUnregisteredError(None)
        run(adapter.revoke(RevokeRequest(Account(PHONE, token=TOKEN))))
