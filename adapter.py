"""
This program is free software: you can redistribute it under the terms
of the GNU General Public License, v. 3.0. If a copy of the GNU General
Public License was not distributed with this file, see <https://www.gnu.org/licenses/>.
"""

import os
import json
import hashlib
import shutil
from typing import Any, Dict, Optional

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
    Load PNBA credentials from a specified configuration dict.
    """
    creds_path = configs.get("credentials", {}).get("path")
    if not creds_path:
        raise ValueError("Missing 'credentials.path' in configuration.")

    creds_path = os.path.expanduser(creds_path)
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
        """
        Initialize the SessionRegistry.

        Args:
            phone_number: The phone number for the session.
            base_path: Optional base directory; defaults to DEFAULT_SESSIONS_DIR.
        """
        self.base_path = base_path or DEFAULT_SESSIONS_DIR
        self.phone_number = phone_number
        self.session_dir = self.get_or_create_session_path(phone_number)
        self.registry_path = os.path.join(self.session_dir, self.REGISTRY_FILENAME)

    def get_or_create_session_path(self, overwrite: bool = False) -> str:
        """
        Get or create the session directory for a given phone number.

        Args:
            overwrite: If True, remove any existing session directory first.

        Returns:
            The absolute path to the session directory.
        """
        os.makedirs(self.base_path, exist_ok=True)

        dirname = hashlib.md5(self.phone_number.encode("utf-8")).hexdigest()
        session_dir = os.path.join(self.base_path, dirname)

        if overwrite and os.path.isdir(session_dir):
            logger.info("Overwriting existing session at %s", session_dir)
            shutil.rmtree(session_dir)

        os.makedirs(session_dir, exist_ok=True)
        return session_dir

    def get_session_file_path(self) -> str:
        """Get the path to the session file."""

        session_name = hashlib.md5(self.phone_number.encode("utf-8")).hexdigest()
        return os.path.join(self.session_dir, session_name)

    def write(self, data: dict) -> None:
        """Write data to the registry file, overwriting any existing data.

        Args:
            data (dict): The dictionary containing data to be stored in the registry.
        """
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def read(self) -> dict:
        """Read and return data from the registry file.

        Returns:
            dict: The data stored in the registry file, or an empty dict if the
                file doesn't exist.
        """
        if not os.path.exists(self.registry_path):
            return {}
        with open(self.registry_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def update(self, **kwargs) -> None:
        """Update the registry with the given key-value pairs.

        Args:
            **kwargs: Key-value pairs to update in the registry. These will be
                merged with existing data, with new values overriding existing ones
                for the same keys.
        """
        data = self.read()
        data.update(kwargs)
        self.write(data)

    def clear(self) -> bool:
        """Clear the registry by deleting the registry file.

        Returns:
            bool: True if the registry was cleared (file existed and was deleted),
                 False if the registry didn't exist.
        """
        if os.path.exists(self.registry_path):
            os.remove(self.registry_path)
            logger.debug("Registry file deleted: %s", self.registry_path)
            return True
        return False


class TelegramPNBAAdapter(PNBAProtocolInterface):
    """
    Adapter for integrating TelegramClient with the PNBA protocol.
    """

    def __init__(self):
        self.credentials = load_credentials(self.config)
        self.session_path: Optional[str] = None
        self.client: Optional[TelegramClient] = None

    async def send_authorization_code(
        self, phone_number: str, base_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send an authorization code to the specified phone number."""

        registry = SessionRegistry(phone_number, base_path)
        self.session_path = registry.get_or_create_session_path(True)
        session_file = registry.get_session_file_path()
        self.client = TelegramClient(
            session=session_file,
            api_id=self.credentials["api_id"],
            api_hash=self.credentials["api_hash"],
        )

        try:
            await self.client.connect()
            if await self.client.is_user_authorized():
                logger.error("User is already authorized.")
                return {
                    "success": False,
                    "message": "User is already authorized.",
                }

            result = await self.client.send_code_request(phone=phone_number)
            registry.update(phone_code_hash=result.phone_code_hash)

            logger.info("Authorization code sent. Check your Telegram app.")

            return {
                "success": True,
                "message": "Authorization code sent. Check your Telegram app.",
            }

        finally:
            await self.client.disconnect()

    async def validate_code_and_fetch_user_info(
        self, phone_number: str, code: str, base_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate the authorization code sent to the phone number and
        retrieve user information.
        """

        registry = SessionRegistry(phone_number, base_path)
        self.session_path = registry.get_or_create_session_path()
        session_file = registry.get_session_file_path()
        self.client = TelegramClient(
            session=session_file,
            api_id=self.credentials["api_id"],
            api_hash=self.credentials["api_hash"],
        )
        phone_code_hash = registry.read().get("phone_code_hash")
        print("Phone code hash:", phone_code_hash)

        try:
            await self.client.connect()
            await self.client.sign_in(
                phone=phone_number, phone_code_hash=phone_code_hash, code=code
            )

            logger.info("User authorized successfully.")

            result = await self.client.get_me()
            registry.clear()

            return {
                "two_step_verification_enabled": False,
                "userinfo": {
                    "account_identifier": phone_number,
                    "name": result.first_name,
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
            await self.client.disconnect()

    async def validate_password_and_fetch_user_info(
        self, phone_number: str, password: str, base_path: Optional[str] = None
    ):
        """Validate the password for two-step verification and retrieve user information."""

        registry = SessionRegistry(phone_number, base_path)
        self.session_path = registry.get_or_create_session_path()
        session_file = registry.get_session_file_path()
        self.client = TelegramClient(
            session=session_file,
            api_id=self.credentials["api_id"],
            api_hash=self.credentials["api_hash"],
        )
        phone_code_hash = registry.read().get("phone_code_hash")

        try:
            await self.client.connect()
            await self.client.sign_in(
                password=password, phone_code_hash=phone_code_hash
            )

            logger.info("User authorized successfully.")

            result = await self.client.get_me()
            registry.clear()

            return {
                "userinfo": {
                    "account_identifier": phone_number,
                    "name": result.first_name,
                },
            }
        finally:
            await self.client.disconnect()

    async def invalidate_session(
        self, phone_number: str, base_path: Optional[str] = None
    ) -> bool:
        """Invalidate the session associated with the phone number."""

        registry = SessionRegistry(phone_number, base_path)
        self.session_path = registry.get_or_create_session_path()
        session_file = registry.get_session_file_path()
        self.client = TelegramClient(
            session=session_file,
            api_id=self.credentials["api_id"],
            api_hash=self.credentials["api_hash"],
        )

        try:
            await self.client.connect()
            await self.client.log_out()
            shutil.rmtree(self.session_path, ignore_errors=True)

            logger.info("Session invalidated successfully.")

            return True
        finally:
            await self.client.disconnect()

    async def send_message(
        self,
        phone_number: str,
        recipient: str,
        message: str,
        base_path: Optional[str] = None,
    ):
        """Send a message to the specified recipient."""

        registry = SessionRegistry(phone_number, base_path)
        self.session_path = registry.get_or_create_session_path()
        session_file = registry.get_session_file_path()
        self.client = TelegramClient(
            session=session_file,
            api_id=self.credentials["api_id"],
            api_hash=self.credentials["api_hash"],
        )

        try:
            await self.client.connect()
            await self.client.send_message(recipient, message)

            logger.info("Message sent successfully.")

            return True
        finally:
            await self.client.disconnect()
