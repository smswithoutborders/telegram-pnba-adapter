# SPDX-License-Identifier: GPL-3.0-only

import io
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, List, Optional, Tuple

from telethon import TelegramClient
from telethon import utils as telethon_utils

from config import Credentials
from session_registry import SessionRegistry


@dataclass
class Attachment:
    """A decoded file ready to send via Telegram."""

    data: bytes
    filename: str
    mimetype: Optional[str] = None


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


def build_client(credentials: Credentials, session_file: Path) -> TelegramClient:
    """Construct a `TelegramClient` bound to a specific account's session file."""
    return TelegramClient(
        session=session_file,
        api_id=credentials.API_ID,
        api_hash=credentials.API_HASH,
    )


@asynccontextmanager
async def client_session(
    credentials: Credentials,
    phone_number: str,
    base_path: Optional[str] = None,
    overwrite: bool = False,
) -> AsyncIterator[Tuple[TelegramClient, SessionRegistry]]:
    """Yield a connected client, disconnecting automatically on exit."""
    registry = SessionRegistry(
        phone_number, credentials, base_path, overwrite=overwrite
    )
    client = build_client(credentials, registry.get_session_file_path())

    await client.connect()
    try:
        yield client, registry
    finally:
        await client.disconnect()
