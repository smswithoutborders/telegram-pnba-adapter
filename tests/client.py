# SPDX-License-Identifier: GPL-3.0-only
"""
Interactive test client for the Telegram PNBA adapter.

Run it with:

    python -m tests.client
"""

import asyncio
import base64
import cmd
import getpass
import json
import shlex
from pathlib import Path


class TelegramAdapterClient(cmd.Cmd):
    intro = "Telegram adapter test client. Type help or ? for a list of commands."
    prompt = "adapter> "

    def __init__(self, adapter):
        super().__init__()
        self.adapter = adapter

    def _call(self, coro, **kwargs):
        """Run an adapter coroutine, pretty-print the result, catch errors."""
        try:
            result = asyncio.run(coro(**kwargs))
        except Exception as e:
            print(f"Error: {e}")
            return None
        print(json.dumps(result, indent=2))
        return result

    def do_send_code(self, line):
        """send_code <phone_number>"""
        phone = line.strip()
        if not phone:
            print("Usage: send_code <phone_number>")
            return
        self._call(self.adapter.send_authorization_code, phone_number=phone)

    def do_verify(self, line):
        """verify <phone_number> <code>"""
        args = line.split()
        if len(args) != 2:
            print("Usage: verify <phone_number> <code>")
            return
        phone, code = args
        result = self._call(
            self.adapter.validate_code_and_fetch_user_info,
            phone_number=phone,
            code=code,
        )
        if result and result.get("two_step_verification_enabled"):
            password = getpass.getpass("Two-step verification password: ")
            self._call(
                self.adapter.validate_password_and_fetch_user_info,
                phone_number=phone,
                password=password,
            )

    def do_validate_password(self, line):
        """validate_password <phone_number> <password>"""
        args = line.split()
        if len(args) != 2:
            print("Usage: validate_password <phone_number> <password>")
            return
        phone, password = args
        self._call(
            self.adapter.validate_password_and_fetch_user_info,
            phone_number=phone,
            password=password,
        )

    def do_send_message(self, line):
        """send_message <phone_number> <recipient> <message> [file_path]"""
        try:
            args = shlex.split(line)
        except ValueError as e:
            print(f"Parse error: {e}")
            return

        if len(args) < 3:
            print(
                "Usage: send_message <phone_number> <recipient> <message> [file_path]"
            )
            return

        phone, recipient, message = args[:3]
        file_path_str = args[3] if len(args) == 4 else None
        attachments = []

        if file_path_str:
            path = Path(file_path_str).expanduser()
            if not path.is_file():
                print(f"Error: Provided path is not a file or does not exist: {path}")
                return
            try:
                b64_data = base64.b64encode(path.read_bytes()).decode("utf-8")
                attachments.append({"data": b64_data, "filename": path.name})
            except Exception as e:
                print(f"Error reading attachment: {e}")
                return

        self._call(
            self.adapter.send_message,
            phone_number=phone,
            recipient=recipient,
            message=message,
            attachments=attachments,
        )

    def do_invalidate(self, line):
        """invalidate <phone_number>"""
        phone = line.strip()
        if not phone:
            print("Usage: invalidate <phone_number>")
            return
        self._call(self.adapter.invalidate_session, phone_number=phone)

    def do_quit(self, _):
        """Exit the client."""
        return True

    do_EOF = do_quit


if __name__ == "__main__":
    from adapter import TelegramPNBAAdapter

    TelegramAdapterClient(TelegramPNBAAdapter()).cmdloop()
