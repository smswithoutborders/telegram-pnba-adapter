# SPDX-License-Identifier: GPL-3.0-only

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from telethon.sessions import SQLiteSession, StringSession

from config import Credentials, load_credentials
from protocol_interfaces import BaseProtocolInterface


def _account_hash(phone_number: str) -> str:
    return hashlib.md5(phone_number.encode("utf-8")).hexdigest()


def _old_session_file(
    credentials: Credentials, assets_path: Optional[str], phone_number: str
) -> Path:
    account_hash = _account_hash(phone_number)
    return (
        credentials.sessions_dir(assets_path) / account_hash / f"{account_hash}.session"
    )


def _extract_session_string(old_session_path: Path) -> str:
    """Read an old SQLiteSession file and re-encode it as a StringSession string."""
    with tempfile.TemporaryDirectory() as tmp:
        # Work on a copy: opening a SQLiteSession can upgrade its schema in place.
        copy_path = Path(tmp) / old_session_path.name
        shutil.copy2(old_session_path, copy_path)

        old = SQLiteSession(str(copy_path.with_suffix("")))
        try:
            new = StringSession()
            new.set_dc(old.dc_id, old.server_address, old.port)
            new.auth_key = old.auth_key
            return new.save()
        finally:
            old._conn.close()


def migrate_sessions(
    assets_path: Optional[str], phone_numbers: List[str], output: str
) -> None:
    credentials = load_credentials(BaseProtocolInterface().config)

    migrated = {}
    skipped = []
    for phone_number in phone_numbers:
        path = _old_session_file(credentials, assets_path, phone_number)
        if not path.is_file():
            print(f"No old session file for {phone_number}: {path}", file=sys.stderr)
            skipped.append(phone_number)
            continue
        try:
            migrated[phone_number] = {"session_string": _extract_session_string(path)}
        except Exception as exc:
            print(f"Failed to migrate {phone_number}: {exc}", file=sys.stderr)
            skipped.append(phone_number)

    Path(output).write_text(json.dumps(migrated, indent=2), encoding="utf-8")

    print(f"Migrated {len(migrated)} session(s) -> {output}")
    if skipped:
        print(f"Skipped {len(skipped)}: {', '.join(skipped)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    migrate = subparsers.add_parser(
        "migrate-sessions",
        help="Convert old per-account SQLiteSession files to session strings.",
    )
    migrate.add_argument(
        "--assets-path",
        help="Directory Publisher passes as base_path for this adapter "
        "(the same value used when the old sessions were created). "
        "Defaults to this adapter's own sessions/ directory if omitted.",
    )
    phones = migrate.add_mutually_exclusive_group(required=True)
    phones.add_argument("--phones", nargs="+", help="Phone numbers to migrate.")
    phones.add_argument("--phones-file", help="File with one phone number per line.")
    migrate.add_argument(
        "--output",
        default="migrated_sessions.json",
        help="Where to write the phone_number to session mapping "
        "(default: %(default)s).",
    )

    args = parser.parse_args()

    if args.phones:
        phone_numbers = args.phones
    else:
        phone_numbers = [
            line.strip()
            for line in Path(args.phones_file).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    migrate_sessions(args.assets_path, phone_numbers, args.output)


if __name__ == "__main__":
    main()
