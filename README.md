# Telegram PNBA Platform Adapter

Lets [RelaySMS Publisher](https://github.com/smswithoutborders/RelaySMS-Publisher) users send Telegram messages from their account, linked with their phone number. Built with the [RelaySMS Adapter SDK](https://github.com/smswithoutborders/RelaySMS-Publisher/tree/main/sdk).

## Settings

Create an application at [my.telegram.org](https://my.telegram.org/) for its `api_id` and `api_hash`, described in [adapter.toml](adapter.toml). On a Publisher, set them up as its [Telegram guide](https://github.com/smswithoutborders/RelaySMS-Publisher/blob/main/docs/platforms/telegram.md) describes.

Logins waiting for a code or password are kept in `pending_auth.sqlite3` in the adapter's state directory for a day.

## Develop

```bash
python3 -m venv venv
venv/bin/pip install -e '.[dev]'
venv/bin/pytest
```

To try it against Telegram, use the [`relaysms-adapter`](https://github.com/smswithoutborders/RelaySMS-Publisher/tree/main/sdk#try-it) console. `link` asks for the code Telegram sends, and the two-step password when the account has one.

```bash
venv/bin/relaysms-adapter config set api_id=12345 api_hash
venv/bin/relaysms-adapter link --phone +237600000000
venv/bin/relaysms-adapter send --to @friend --body hello --attach ./photo.jpg
venv/bin/relaysms-adapter revoke
```
