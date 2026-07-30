# SPDX-License-Identifier: GPL-3.0-only

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from logutils import get_logger

logger = get_logger(__name__)

_PACKAGE_DIR = Path(__file__).parent

DEFAULT_SESSIONS_DIRNAME = "sessions"
DEFAULT_REGISTRY_FILENAME = "registry.json"


@dataclass
class Credentials:
    API_ID: int
    API_HASH: str
    SESSIONS_DIR: Optional[str] = None
    REGISTRY_FILENAME: str = DEFAULT_REGISTRY_FILENAME

    def sessions_dir(self, base_path: Optional[str] = None) -> Path:
        if base_path:
            return Path(base_path).expanduser()
        if self.SESSIONS_DIR:
            return Path(self.SESSIONS_DIR).expanduser()
        return _PACKAGE_DIR / DEFAULT_SESSIONS_DIRNAME


_REQUIRED_FIELDS = {"api_id", "api_hash"}


def _resolve_creds_path(configs: Dict[str, Any]) -> Path:
    creds_config = configs.get("credentials", {})
    raw_path = creds_config.get("path", "")
    if not raw_path:
        raise ValueError("Missing 'credentials.path' in configuration.")

    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path(__file__).parent / path
    return path


def _check_str_field(creds: Dict[str, Any], field: str, required: bool) -> None:
    if field not in creds:
        return
    if not isinstance(creds[field], str) or not creds[field].strip():
        suffix = "." if required else " when provided."
        raise ValueError(f"'{field}' must be a non-empty string{suffix}")


def _validate_creds(creds: Dict[str, Any]) -> None:
    missing = _REQUIRED_FIELDS - creds.keys()
    if missing:
        raise ValueError(
            f"Missing required credential fields: {', '.join(sorted(missing))}"
        )

    _check_str_field(creds, "api_hash", required=True)

    for field in ("sessions_dir", "registry_filename"):
        _check_str_field(creds, field, required=False)


def load_credentials(configs: Dict[str, Any]) -> Credentials:
    """Load, validate, and return a Credentials instance from the specified path."""
    path = _resolve_creds_path(configs)
    logger.debug("Loading credentials from %s", path)

    try:
        with path.open(encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Credentials file not found: {path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Credentials file is not valid JSON: {e}")

    _validate_creds(raw)

    return Credentials(
        API_ID=int(raw["api_id"]),
        API_HASH=raw["api_hash"],
        SESSIONS_DIR=raw.get("sessions_dir"),
        REGISTRY_FILENAME=raw.get("registry_filename", DEFAULT_REGISTRY_FILENAME),
    )
