# SPDX-License-Identifier: GPL-3.0-only

import hashlib
import json
import shutil
from pathlib import Path
from typing import Optional

from config import Credentials
from logutils import get_logger

logger = get_logger(__name__)


class SessionRegistry:
    """Helper for managing Telegram sessions and registry files."""

    def __init__(
        self,
        phone_number: str,
        credentials: Credentials,
        base_path: Optional[str] = None,
        overwrite: bool = False,
    ):
        self.phone_number = phone_number
        self.base_path = credentials.sessions_dir(base_path)
        self.registry_filename = credentials.REGISTRY_FILENAME
        self._account_hash = hashlib.md5(phone_number.encode("utf-8")).hexdigest()
        self.session_dir = self._get_or_create_session_path(overwrite=overwrite)
        self.registry_path = self.session_dir / self.registry_filename

    def _get_or_create_session_path(self, overwrite: bool = False) -> Path:
        session_path = self.base_path / self._account_hash

        if overwrite and session_path.exists():
            logger.info("Overwriting existing session at %s", session_path)
            shutil.rmtree(session_path)

        session_path.mkdir(parents=True, exist_ok=True)
        return session_path

    def get_session_file_path(self) -> Path:
        return self.session_dir / self._account_hash

    def invalidate(self) -> None:
        """Remove this account's entire session directory from disk."""
        shutil.rmtree(self.session_dir, ignore_errors=True)

    def read(self) -> dict:
        if not self.registry_path.exists():
            return {}
        return json.loads(self.registry_path.read_text(encoding="utf-8"))

    def write(self, data: dict) -> None:
        self.registry_path.write_text(json.dumps(data), encoding="utf-8")

    def update(self, **kwargs) -> None:
        data = self.read()
        data.update(kwargs)
        self.write(data)

    def clear(self) -> bool:
        if self.registry_path.exists():
            self.registry_path.unlink()
            logger.debug("Registry cleared: %s", self.registry_path)
            return True
        return False
