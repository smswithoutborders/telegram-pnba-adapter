# SPDX-License-Identifier: GPL-3.0-only
"""The Telegram API application from my.telegram.org."""

from dataclasses import dataclass

from relaysms_adapter_sdk import read_config


@dataclass(frozen=True)
class Credentials:
    api_id: int
    api_hash: str


def load() -> Credentials:
    """Read credentials.json from the adapter's config directory.

    Raises:
        ValueError: The file is invalid.
    """
    raw = read_config()
    try:
        api_id = int(raw["api_id"])
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"credentials.json needs a numeric api_id: {e}") from e
    if not isinstance(raw.get("api_hash"), str) or not raw["api_hash"].strip():
        raise ValueError("api_hash in credentials.json must be a non-empty string.")
    return Credentials(api_id=api_id, api_hash=raw["api_hash"])
