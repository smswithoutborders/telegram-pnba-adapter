# SPDX-License-Identifier: GPL-3.0-only
"""The Telegram API application from my.telegram.org."""

import json
from dataclasses import dataclass

from relaysms_adapter_sdk import config_dir

FILENAME = "credentials.json"


@dataclass(frozen=True)
class Credentials:
    api_id: int
    api_hash: str


def load() -> Credentials:
    """Read credentials.json from the adapter's config directory.

    Raises:
        ValueError: The file is invalid.
    """
    path = config_dir() / FILENAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        api_id = int(raw["api_id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        raise ValueError(f"{path} needs a numeric api_id: {e}") from e
    if not isinstance(raw.get("api_hash"), str) or not raw["api_hash"].strip():
        raise ValueError(f"api_hash in {path} must be a non-empty string.")
    return Credentials(api_id=api_id, api_hash=raw["api_hash"])
