# Telegram PNBA Platform Adapter

Lets [RelaySMS Publisher](https://github.com/smswithoutborders/RelaySMS-Publisher) users send Telegram messages from their account, linked with their phone number. Built with the [RelaySMS Adapter SDK](https://github.com/smswithoutborders/RelaySMS-Publisher/tree/main/sdk).

## Credentials

Create an application at [my.telegram.org](https://my.telegram.org/) and put its `credentials.json` in the adapter's config directory. The Publisher keeps it at `data/platforms/config/<adapter id>/credentials.json`.

```json
{
  "api_id": "12345",
  "api_hash": "0123456789abcdef0123456789abcdef"
}
```

Logins waiting for a code or password are kept in `pending_auth.sqlite3` in the adapter's state directory for a day.

## Develop

```bash
python3 -m venv venv
venv/bin/pip install -e '.[dev]'
venv/bin/pytest
```

To try it against Telegram, put `credentials.json` in `.relaysms/config/` and use the [`relaysms-adapter`](https://github.com/smswithoutborders/RelaySMS-Publisher/tree/main/sdk#try-it) console. It asks for the code Telegram sends, and the two-step password when the account has one.

```bash
venv/bin/relaysms-adapter link --phone +237600000000
venv/bin/relaysms-adapter send --to @friend --body hello --attach ./photo.jpg
venv/bin/relaysms-adapter revoke
```
