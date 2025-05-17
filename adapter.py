"""
This program is free software: you can redistribute it under the terms
of the GNU General Public License, v. 3.0. If a copy of the GNU General
Public License was not distributed with this file, see <https://www.gnu.org/licenses/>.
"""

import os
import json
import hashlib
import shutil
from typing import Any, Dict, Optional, Tuple

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from protocol_interfaces import PNBAProtocolInterface
from logutils import get_logger

logger = get_logger(__name__)

DEFAULT_SESSIONS_DIR = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "sessions"
)
os.makedirs(DEFAULT_SESSIONS_DIR, exist_ok=True)


def load_credentials(configs: Dict[str, Any]) -> Dict[str, str]:
    """
    Load PNBA credentials from the specified configuration dict.
    """
    creds_config = configs.get("credentials", {})
    creds_path = os.path.expanduser(creds_config.get("path", ""))
    if not creds_path:
        raise ValueError("Missing 'credentials.path' in configuration.")
    if not os.path.isabs(creds_path):
        creds_path = os.path.join(os.path.dirname(__file__), creds_path)

    logger.debug("Loading credentials from %s", creds_path)
    with open(creds_path, encoding="utf-8") as f:
        creds = json.load(f)

    return {"api_id": creds["api_id"], "api_hash": creds["api_hash"]}


class SessionRegistry:
    """Helper for managing Telegram sessions and registry files."""

    REGISTRY_FILENAME = "registry.json"

    def __init__(self, phone_number: str, base_path: Optional[str] = None):
        self.phone_number = phone_number
        self.base_path = base_path or DEFAULT_SESSIONS_DIR
        self.session_dir = self._get_or_create_session_path()
        self.registry_path = os.path.join(self.session_dir, self.REGISTRY_FILENAME)

    def _get_or_create_session_path(self, overwrite: bool = False) -> str:
        os.makedirs(self.base_path, exist_ok=True)
        dir_name = hashlib.md5(self.phone_number.encode("utf-8")).hexdigest()
        session_path = os.path.join(self.base_path, dir_name)

        if overwrite and os.path.exists(session_path):
            logger.info("Overwriting existing session at %s", session_path)
            shutil.rmtree(session_path)

        os.makedirs(session_path, exist_ok=True)
        return session_path

    def get_session_file_path(self) -> str:
        filename = hashlib.md5(self.phone_number.encode("utf-8")).hexdigest()
        return os.path.join(self.session_dir, filename)

    def read(self) -> dict:
        if not os.path.exists(self.registry_path):
            return {}
        with open(self.registry_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def write(self, data: dict) -> None:
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def update(self, **kwargs) -> None:
        data = self.read()
        data.update(kwargs)
        self.write(data)

    def clear(self) -> bool:
        if os.path.exists(self.registry_path):
            os.remove(self.registry_path)
            logger.debug("Registry cleared: %s", self.registry_path)
            return True
        return False


class TelegramPNBAAdapter(PNBAProtocolInterface):
    """Adapter for integrating TelegramClient with the PNBA protocol."""

    def __init__(self):
        self.credentials = load_credentials(self.config)
        self.session_path: Optional[str] = None
        self.client: Optional[TelegramClient] = None

    def _get_client_and_registry(
        self,
        phone_number: str,
        base_path: Optional[str] = None,
        overwrite: bool = False,
    ) -> Tuple[TelegramClient, SessionRegistry, str]:
        registry = SessionRegistry(phone_number, base_path)
        session_path = registry._get_or_create_session_path(overwrite=overwrite)
        session_file = registry.get_session_file_path()

        client = TelegramClient(
            session=session_file,
            api_id=self.credentials["api_id"],
            api_hash=self.credentials["api_hash"],
        )
        return client, registry, session_path

    async def send_authorization_code(
        self, phone_number: str, **kwargs
    ) -> Dict[str, Any]:
        base_path = kwargs.get("base_path", None)
        client, registry, _ = self._get_client_and_registry(
            phone_number, base_path, overwrite=True
        )

        try:
            await client.connect()
            if await client.is_user_authorized():
                logger.warning("User already authorized.")
                return {"success": False, "message": "User already authorized."}

            result = await client.send_code_request(phone=phone_number)
            registry.update(phone_code_hash=result.phone_code_hash)

            logger.info("Authorization code sent.")
            return {"success": True, "message": "Authorization code sent."}

        finally:
            await client.disconnect()

    async def validate_code_and_fetch_user_info(
        self, phone_number: str, code: str, **kwargs
    ) -> Dict[str, Any]:
        base_path = kwargs.get("base_path", None)
        client, registry, _ = self._get_client_and_registry(phone_number, base_path)
        phone_code_hash = registry.read().get("phone_code_hash")

        if not phone_code_hash:
            logger.warning("Missing phone_code_hash in registry.")

        try:
            await client.connect()
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
        finally:
            await client.disconnect()

    async def validate_password_and_fetch_user_info(
        self, phone_number: str, password: str, **kwargs
    ) -> Dict[str, Any]:
        base_path = kwargs.get("base_path", None)
        client, registry, _ = self._get_client_and_registry(phone_number, base_path)

        try:
            await client.connect()
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
        finally:
            await client.disconnect()

    async def invalidate_session(self, phone_number: str, **kwargs) -> bool:
        base_path = kwargs.get("base_path", None)
        client, _, session_path = self._get_client_and_registry(phone_number, base_path)

        try:
            await client.connect()
            await client.log_out()
            shutil.rmtree(session_path, ignore_errors=True)

            logger.info("Session invalidated.")
            return True
        finally:
            await client.disconnect()

    async def send_message(
        self, phone_number: str, recipient: str, message: str, **kwargs
    ) -> bool:
        base_path = kwargs.get("base_path", None)
        client, _, _ = self._get_client_and_registry(phone_number, base_path)

        try:
            await client.connect()
            await client.send_message(recipient, message)

            logger.info("Message sent to %s", recipient)
            return True
        finally:
            await client.disconnect()
