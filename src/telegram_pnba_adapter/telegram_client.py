# SPDX-License-Identifier: GPL-3.0-only

import io
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from relaysms_adapter_sdk import Attachment
from telethon import TelegramClient
from telethon import utils as telethon_utils
from telethon.sessions import StringSession

from telegram_pnba_adapter.credentials import Credentials


@dataclass
class SessionSnapshot:
    session_string: str | None = None


def to_telegram_file(attachment: Attachment) -> io.BytesIO:
    """Wrap attachment bytes in a named buffer Telethon can send as a file."""
    buffer = io.BytesIO(attachment.data)
    buffer.name = attachment.filename
    return buffer


def should_force_document(attachments: tuple[Attachment, ...]) -> bool:
    """True if any attachment isn't a format Telethon recognizes as a plain photo.

    Formats like `.webp` get auto-tagged as stickers by Telegram's servers when sent
    as photos, and no official Telegram client renders a caption on a sticker message.
    Forcing those through as plain documents keeps the caption visible.
    """
    return not all(telethon_utils.is_image(a.filename) for a in attachments)


def build_client(credentials: Credentials, session: StringSession) -> TelegramClient:
    return TelegramClient(
        session=session,
        api_id=credentials.api_id,
        api_hash=credentials.api_hash,
    )


@asynccontextmanager
async def client_session(
    credentials: Credentials, session_string: str | None = None
) -> AsyncIterator[tuple[TelegramClient, SessionSnapshot]]:
    session = StringSession(session_string) if session_string else StringSession()
    client = build_client(credentials, session)
    snapshot = SessionSnapshot()

    await client.connect()
    try:
        yield client, snapshot
    finally:
        try:
            if client.session is not None:
                snapshot.session_string = client.session.save()
        finally:
            await client.disconnect()
