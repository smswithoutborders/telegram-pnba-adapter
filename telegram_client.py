# SPDX-License-Identifier: GPL-3.0-only

import io
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, List, Optional, Tuple

from telethon import TelegramClient
from telethon import utils as telethon_utils
from telethon.sessions import StringSession

from config import Credentials


@dataclass
class Attachment:
    """A decoded file ready to send via Telegram."""

    data: bytes
    filename: str
    mimetype: Optional[str] = None


@dataclass
class SessionSnapshot:
    session_string: Optional[str] = None


def to_telegram_file(attachment: Attachment) -> io.BytesIO:
    """Wrap attachment bytes in a named buffer Telethon can send as a file."""
    buffer = io.BytesIO(attachment.data)
    buffer.name = attachment.filename
    return buffer


def should_force_document(attachments: List[Attachment]) -> bool:
    """True if any attachment isn't a format Telethon recognizes as a plain photo.

    Formats like `.webp` get auto-tagged as stickers by Telegram's servers when sent
    as photos, and no official Telegram client renders a caption on a sticker message.
    Forcing those through as plain documents keeps the caption visible.
    """
    return not all(telethon_utils.is_image(a.filename) for a in attachments)


def build_client(credentials: Credentials, session: StringSession) -> TelegramClient:
    return TelegramClient(
        session=session,
        api_id=credentials.API_ID,
        api_hash=credentials.API_HASH,
    )


@asynccontextmanager
async def client_session(
    credentials: Credentials, session_string: Optional[str] = None
) -> AsyncIterator[Tuple[TelegramClient, SessionSnapshot]]:
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
