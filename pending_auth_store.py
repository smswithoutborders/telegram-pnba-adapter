# SPDX-License-Identifier: GPL-3.0-only

import hashlib
import hmac
import sqlite3
import time
from pathlib import Path
from typing import NamedTuple, Optional

from config import Credentials

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_auth (
    phone_number_hash TEXT PRIMARY KEY,
    phone_code_hash TEXT NOT NULL,
    session_string TEXT NOT NULL,
    created_at REAL NOT NULL
)
"""

_MAX_AGE_SECONDS = 24 * 60 * 60
_BUSY_TIMEOUT_MS = 5000


class PendingAuth(NamedTuple):
    phone_code_hash: str
    session_string: str


class PendingAuthStore:
    def __init__(self, credentials: Credentials, base_path: Optional[str] = None):
        self._hmac_key = credentials.API_HASH.encode("utf-8")

        db_path = credentials.sessions_dir(base_path) / credentials.REGISTRY_FILENAME
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, timeout=_BUSY_TIMEOUT_MS / 1000)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
        self._conn.execute(_SCHEMA)
        self._conn.execute(
            "DELETE FROM pending_auth WHERE created_at < ?",
            (time.time() - _MAX_AGE_SECONDS,),
        )
        self._conn.commit()

    def _key(self, phone_number: str) -> str:
        return hmac.new(
            self._hmac_key, phone_number.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def set(self, phone_number: str, phone_code_hash: str, session_string: str) -> None:
        self._conn.execute(
            "INSERT INTO pending_auth "
            "(phone_number_hash, phone_code_hash, session_string, created_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(phone_number_hash) DO UPDATE SET "
            "phone_code_hash = excluded.phone_code_hash, "
            "session_string = excluded.session_string, "
            "created_at = excluded.created_at",
            (self._key(phone_number), phone_code_hash, session_string, time.time()),
        )
        self._conn.commit()

    def get(self, phone_number: str) -> Optional[PendingAuth]:
        row = self._conn.execute(
            "SELECT phone_code_hash, session_string FROM pending_auth "
            "WHERE phone_number_hash = ?",
            (self._key(phone_number),),
        ).fetchone()
        return PendingAuth(*row) if row else None

    def clear(self, phone_number: str) -> None:
        self._conn.execute(
            "DELETE FROM pending_auth WHERE phone_number_hash = ?",
            (self._key(phone_number),),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "PendingAuthStore":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
