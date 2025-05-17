# Telegram PNBA Platform Adapter

This adapter provides a pluggable implementation for integrating Telegram as a messaging platform. It is designed to work with [RelaySMS Publisher](https://github.com/smswithoutborders/RelaySMS-Publisher), enabling users to connect to Telegram using PNBA (Phone number-based authentication) authentication.

## Requirements

- **Python**: Version >=
  [3.8.10](https://www.python.org/downloads/release/python-3810/)
- **Python Virtual Environments**:
  [Documentation](https://docs.python.org/3/tutorial/venv.html)

## Dependencies

### On Ubuntu

Install the necessary system packages:

```bash
sudo apt install build-essential python3-dev
```

## Installation

1. **Create a virtual environment:**

   ```bash
   python3 -m venv venv
   ```

2. **Activate the virtual environment:**

   ```bash
   . venv/bin/activate
   ```

3. **Install the required Python packages:**

   ```bash
   # For production use
   pip install -r requirements.txt

   # For development and testing (includes CLI tools)
   pip install -r test-requirements.txt
   ```

## Configuration

1. Obtain your credentials from the [Telegram Developer Portal](https://my.telegram.org/).
2. Set the `credentials.json` path of your credentials file in the `manifest.ini`:

```ini
   [credentials]
   path = ./credentials.json
```

**Sample `credentials.json`**

```json
{
  "api_id": "",
  "api_hash": ""
}
```

## CLI Usage

The adapter comes with a command-line interface (CLI) that allows you to test all functionality directly from the terminal.

### Getting Started

To see all available commands:

```bash
python telegram_cli.py --help
```

To use the interactive mode which provides a menu interface:

```bash
python telegram_cli.py --interactive
```

or

```bash
python telegram_cli.py -i
```

### Authentication Commands

**Send Authentication Code:**

```bash
python telegram_cli.py auth:send-code --phone="+1234567890"
```

**Validate Authentication Code:**

```bash
python telegram_cli.py auth:validate-code --phone="+1234567890" --code="12345"
```

**Validate Two-Step Verification Password:**

```bash
python telegram_cli.py auth:validate-password --phone="+1234567890" --password="your_password"
```

### Messaging Commands

**Send a Message:**

```bash
python telegram_cli.py message:send --phone="+1234567890" --recipient="@username" --text="Hello from CLI"
```

### Session Management

**Invalidate a Session:**

```bash
python telegram_cli.py session:invalidate --phone="+1234567890"
```

> [!TIP]
>
> If you don't provide required options, the CLI will prompt you for them:
>
> ```bash
> python telegram_cli.py message:send
> ```

> [!TIP]
>
> To get help for a specific command:
>
> ```bash
> python telegram_cli.py auth:send-code --help
> ```
