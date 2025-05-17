"""
This program is free software: you can redistribute it under the terms
of the GNU General Public License, v. 3.0. If a copy of the GNU General
Public License was not distributed with this file, see <https://www.gnu.org/licenses/>.
"""

import os
import asyncio
import json
import sys
import click

from adapter import TelegramPNBAAdapter
from logutils import get_logger

logger = get_logger(__name__)


def interactive_mode(ctx, param, value):
    """Start an interactive session if the flag is provided."""
    if not value or ctx.resilient_parsing:
        return
    app = InteractiveApp()
    app.start()
    ctx.exit()


@click.group()
@click.option(
    "-i",
    "--interactive",
    is_flag=True,
    help="Start an interactive session",
    callback=interactive_mode,
    expose_value=False,
)
def cli():
    """Telegram PNBA Adapter Command Line Interface.

    This tool allows you to test all functions of the TelegramPNBAAdapter.
    """


@cli.command("auth:send-code")
@click.option(
    "--phone", prompt=True, help="Phone number with country code (e.g. +1234567890)"
)
def send_auth_code(phone):
    """Send authorization code to the specified phone number."""
    adapter = TelegramPNBAAdapter()

    async def run():
        click.echo("Sending authorization code...")
        result = await adapter.send_authorization_code(phone)
        click.echo(f"Result: {json.dumps(result, indent=2)}")

    asyncio.run(run())


@cli.command("auth:validate-code")
@click.option("--phone", prompt=True, help="Phone number with country code")
@click.option("--code", prompt=True, help="Authorization code received")
def validate_code(phone, code):
    """Validate authorization code and fetch user info."""
    adapter = TelegramPNBAAdapter()

    async def run():
        click.echo("Validating code...")
        result = await adapter.validate_code_and_fetch_user_info(phone, code)
        click.echo(f"Result: {json.dumps(result, indent=2)}")

    asyncio.run(run())


@cli.command("auth:validate-password")
@click.option("--phone", prompt=True, help="Phone number with country code")
@click.option(
    "--password", prompt=True, hide_input=True, help="Two-step verification password"
)
def validate_password(phone, password):
    """Validate two-step verification password and fetch user info."""
    adapter = TelegramPNBAAdapter()

    async def run():
        click.echo("Validating password...")
        result = await adapter.validate_password_and_fetch_user_info(phone, password)
        click.echo(f"Result: {json.dumps(result, indent=2)}")

    asyncio.run(run())


@cli.command("message:send")
@click.option("--phone", prompt=True, help="Your phone number with country code")
@click.option("--recipient", prompt=True, help="Recipient's phone number or username")
@click.option("--text", prompt=True, help="Message text to send")
def send_message(phone, recipient, text):
    """Send a message to a recipient."""
    adapter = TelegramPNBAAdapter()

    async def run():
        click.echo("Sending message...")
        result = await adapter.send_message(phone, recipient, text)
        click.echo(f"Message sent: {result}")

    asyncio.run(run())


@cli.command("session:invalidate")
@click.option("--phone", prompt=True, help="Phone number to invalidate session for")
def invalidate_session(phone):
    """Invalidate a session for a phone number."""
    adapter = TelegramPNBAAdapter()

    async def run():
        click.echo("Invalidating session...")
        result = await adapter.invalidate_session(phone)
        click.echo(f"Session invalidated: {result}")

    asyncio.run(run())


class InteractiveApp:
    """Interactive application mode."""

    def __init__(self):
        self.adapter = TelegramPNBAAdapter()
        self.state = {
            "phone": None,
            "authenticated": False,
        }
        self.main_menu = [
            {"number": 1, "title": "Set Phone Number", "action": self.set_phone},
            {"number": 2, "title": "Authentication", "action": self.show_auth_menu},
            {"number": 3, "title": "Send Message", "action": self.send_message},
            {
                "number": 4,
                "title": "Invalidate Session",
                "action": self.invalidate_session,
            },
            {"number": 5, "title": "Show Status", "action": self.show_status},
            {"number": 0, "title": "Exit", "action": self.exit_app},
        ]
        self.auth_menu = [
            {
                "number": 1,
                "title": "Send Authorization Code",
                "action": self.send_auth_code,
            },
            {"number": 2, "title": "Validate Code", "action": self.validate_code},
            {
                "number": 3,
                "title": "Validate Password",
                "action": self.validate_password,
            },
            {"number": 0, "title": "Back to Main Menu", "action": self.show_main_menu},
        ]
        self.current_menu = self.main_menu

    def start(self):
        """Start the interactive command loop."""
        self.clear_screen()
        click.echo("Starting Telegram PNBA Adapter Interactive Mode")
        click.echo("=" * 50)
        self.show_main_menu()

    def clear_screen(self):
        """Clear the terminal screen."""
        os.system("clear")

    def display_menu(self, menu, title):
        """Display a menu with numeric options."""
        self.clear_screen()
        click.echo(f"Telegram PNBA Adapter - {title}")
        click.echo("=" * 50)

        if self.state["phone"]:
            click.echo(
                f"Phone: {self.state['phone']} | "
                f"Authenticated: {'Yes' if self.state['authenticated'] else 'No'}"
            )
            click.echo("-" * 50)

        for item in menu:
            click.echo(f"{item['number']}. {item['title']}")

        choice = click.prompt("\nEnter your choice", type=int)

        for item in menu:
            if item["number"] == choice:
                item["action"]()
                return

        click.echo("Invalid choice. Please try again.")
        click.pause()
        self.display_menu(menu, title)

    def show_main_menu(self):
        """Show the main menu."""
        self.current_menu = self.main_menu
        self.display_menu(self.main_menu, "Main Menu")

    def show_auth_menu(self):
        """Show the authentication menu."""
        self.current_menu = self.auth_menu
        self.display_menu(self.auth_menu, "Authentication Menu")

    def exit_app(self):
        """Exit the application."""
        click.echo("\nExiting interactive mode...")
        sys.exit(0)

    def show_status(self):
        """Show the current session status."""
        self.clear_screen()
        click.echo("Current Session Status")
        click.echo("=" * 50)
        click.echo(f"Phone Number: {self.state['phone'] or 'Not set'}")
        click.echo(f"Authenticated: {self.state['authenticated']}")
        click.echo("=" * 50)
        click.pause("\nPress any key to return to the menu...")
        self.display_menu(
            self.current_menu,
            (
                "Main Menu"
                if self.current_menu == self.main_menu
                else "Authentication Menu"
            ),
        )

    def set_phone(self):
        """Set the phone number for the session."""
        self.clear_screen()
        click.echo("Set Phone Number")
        click.echo("=" * 50)

        phone = click.prompt("Enter phone number with country code (e.g. +1234567890)")
        self.state["phone"] = phone
        click.echo(f"\nPhone number set to: {phone}")
        click.pause("\nPress any key to return to the menu...")
        self.display_menu(
            self.current_menu,
            (
                "Main Menu"
                if self.current_menu == self.main_menu
                else "Authentication Menu"
            ),
        )

    def _ensure_phone(self):
        """Ensure a phone number is available."""
        if not self.state["phone"]:
            click.echo("Phone number is not set.")
            self.set_phone()
        return self.state["phone"]

    def send_auth_code(self):
        """Send authorization code to the configured phone number."""
        self.clear_screen()
        click.echo("Send Authorization Code")
        click.echo("=" * 50)

        phone = self._ensure_phone()

        async def run():
            click.echo(f"Sending authorization code to {phone}...")
            try:
                result = await self.adapter.send_authorization_code(phone)
                click.echo(f"\nResult: {json.dumps(result, indent=2)}")
            except Exception as e:
                click.echo(f"\nFailed to send code: {str(e)}")

        asyncio.run(run())
        click.pause("\nPress any key to return to the menu...")
        self.display_menu(
            self.current_menu,
            (
                "Main Menu"
                if self.current_menu == self.main_menu
                else "Authentication Menu"
            ),
        )

    def validate_code(self):
        """Validate authorization code and fetch user info."""
        self.clear_screen()
        click.echo("Validate Authorization Code")
        click.echo("=" * 50)

        phone = self._ensure_phone()
        code = click.prompt("Enter authorization code received")

        async def run():
            click.echo("\nValidating code...")
            try:
                result = await self.adapter.validate_code_and_fetch_user_info(
                    phone, code
                )
                click.echo(f"\nResult: {json.dumps(result, indent=2)}")
                self.state["authenticated"] = True
            except Exception as e:
                click.echo(f"\nCode validation failed: {str(e)}")

        asyncio.run(run())
        click.pause("\nPress any key to return to the menu...")
        self.display_menu(
            self.current_menu,
            (
                "Main Menu"
                if self.current_menu == self.main_menu
                else "Authentication Menu"
            ),
        )

    def validate_password(self):
        """Validate two-step verification password and fetch user info."""
        self.clear_screen()
        click.echo("Validate Two-Step Verification Password")
        click.echo("=" * 50)

        phone = self._ensure_phone()
        password = click.prompt("Enter two-step verification password", hide_input=True)

        async def run():
            click.echo("\nValidating password...")
            try:
                result = await self.adapter.validate_password_and_fetch_user_info(
                    phone, password
                )
                click.echo(f"\nResult: {json.dumps(result, indent=2)}")
                self.state["authenticated"] = True
            except Exception as e:
                click.echo(f"\nPassword validation failed: {str(e)}")

        asyncio.run(run())
        click.pause("\nPress any key to return to the menu...")
        self.display_menu(
            self.current_menu,
            (
                "Main Menu"
                if self.current_menu == self.main_menu
                else "Authentication Menu"
            ),
        )

    def send_message(self):
        """Send a message to a recipient."""
        self.clear_screen()
        click.echo("Send Message")
        click.echo("=" * 50)

        phone = self._ensure_phone()
        recipient = click.prompt("Enter recipient (phone number or username)")
        text = click.prompt("Enter message text")

        async def run():
            click.echo(f"\nSending message to {recipient}...")
            try:
                result = await self.adapter.send_message(phone, recipient, text)
                click.echo(f"\nMessage sent: {result}")
            except Exception as e:
                click.echo(f"\nFailed to send message: {str(e)}")

        asyncio.run(run())
        click.pause("\nPress any key to return to the menu...")
        self.display_menu(
            self.current_menu,
            (
                "Main Menu"
                if self.current_menu == self.main_menu
                else "Authentication Menu"
            ),
        )

    def invalidate_session(self):
        """Invalidate the current session."""
        self.clear_screen()
        click.echo("Invalidate Session")
        click.echo("=" * 50)

        phone = self._ensure_phone()

        async def run():
            click.echo("\nInvalidating session...")
            try:
                result = await self.adapter.invalidate_session(phone)
                click.echo(f"\nSession invalidated: {result}")
                self.state["authenticated"] = False
            except Exception as e:
                click.echo(f"\nFailed to invalidate session: {str(e)}")

        asyncio.run(run())
        click.pause("\nPress any key to return to the menu...")
        self.display_menu(
            self.current_menu,
            (
                "Main Menu"
                if self.current_menu == self.main_menu
                else "Authentication Menu"
            ),
        )


if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\nOperation interrupted. Exiting...")
        sys.exit(1)
    except Exception as e:
        click.echo(f"An error occurred: {str(e)}", err=True)
        sys.exit(1)
