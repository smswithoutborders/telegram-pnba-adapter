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
   pip install -r requirements.txt
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

## Testing

```bash
python -m tests.client
```

Available commands:

```
send_code <phone_number>
verify <phone_number> <code>
validate_password <phone_number> <password>
send_message <phone_number> <recipient> <message> [file_path]
invalidate <phone_number>
quit
```

## Keeping Interfaces Up to Date

If you suspect that `protocol_interfaces.py` is outdated or inconsistent with the host platform, sync it using:

```bash
curl -fsSL -o protocol_interfaces.py https://raw.githubusercontent.com/smswithoutborders/RelaySMS-Publisher/main/platforms/protocol_interfaces.py
```
