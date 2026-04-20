# discord-bot

A Pycord-based Discord bot with a few focused integrations:

- **Dice rolling** via slash command (`/roll`) using [`d20`](https://d20.readthedocs.io/).
- **Self-assignable roles** via persistent button menus.
- **RabbitMQ → Discord bridge** for sending messages (including small attachments) from external producers.
- **Discord → Telegram relay** *(not implemented yet)*.

## Tech stack

- Python **3.14+**
- [uv](https://docs.astral.sh/uv/) for dependency management
- [Pycord](https://docs.pycord.dev/en/stable/) (`py-cord[speed]`)
- RabbitMQ (`aio-pika`)
- Telegram Bot API (`python-telegram-bot`)
- `pydantic-settings` for config loading

## Project structure

```text
.
├── main.py
├── src/
│   ├── bot.py               # Bot setup + cog loading
│   ├── config.py            # Settings models / loading
│   └── cogs/
│       ├── dice.py          # /roll command
│       ├── roles.py         # Role buttons + /menu command
│       ├── rabbit.py        # RabbitMQ consumer + Discord sender
│       └── tg.py            # Discord->Telegram relay
├── settings.json.example
├── pyproject.toml
└── Dockerfile
```

## Configuration

Settings are loaded by `pydantic-settings` from:

1. `settings.json` (JSON source)
2. `.env` (dotenv source)

The bot expects these secret/env keys:

- `TOKEN` (Discord token)
- `RABBIT` (RabbitMQ DSN)
- `TELEGRAM_TOKEN` (Telegram bot token)

And these JSON settings (see `settings.json.example`):

- `telegram_channel`
- `discord_guild_name`
- `discord_channel_name`
- `discord_debug_channel_name`
- `discord_welcome_channel_name`
- `discord_news_channel_name`
- `discord_role_names`
- `roles` (list of role button descriptors)

### Quick start config files

Create a `.env` file:

```env
TOKEN=discord-bot-token
RABBIT=amqp://guest:guest@localhost:5672/
TELEGRAM_TOKEN=telegram-bot-token
```

Create a `settings.json` file from the example:

```bash
cp settings.json.example settings.json
```

Then fill in values in `settings.json`.

## Local development

Install dependencies with `uv`:

```bash
uv sync
```

Run the bot:

```bash
python main.py
```

> Note: both local and Docker entrypoints now use `main.py`.

## Docker

Build image:

```bash
docker build -t discord-bot .
```

Run container (example):

```bash
docker run --rm \
  --env-file .env \
  -v "$(pwd)/settings.json:/app/settings.json:ro" \
  discord-bot
```

## Commands and behavior

### `/roll`

- Available in the configured dice channel (or debug channel).
- Supports `d20` expressions (for example: `2d20kh1 + 5`).
- `/roll help` returns a syntax reference link.

### `/menu`

Posts a role-selection message with persistent buttons. Clicking a button toggles a role for the user.

## RabbitMQ message format

The Rabbit consumer declares queue `discord` and validates payloads against this schema:

```json
{
  "expires_at": "2026-01-01T12:00:00+00:00",
  "action": "send",
  "body": "Hello from RabbitMQ",
  "channel": "optional-channel-name",
  "attachment": {
    "filename": "report.txt",
    "data_b64": "<base64 file bytes>"
  }
}
```

Notes:

- `expires_at` is enforced; expired messages are discarded.
- Attachment max size is **8 MiB**.
- `@RoleName` strings in `body` are converted to configured Discord role mentions.

## Telegram relay status

Telegram integration is planned, but **not implemented yet** in production-ready form.

Current repository contains experimental Telegram-related code, but it should be treated as work in progress.

## Troubleshooting

- **Bot cannot find guild/channel/role**: verify names in `settings.json` exactly match Discord.
- **Rabbit messages ignored**: confirm `expires_at` is in the future and JSON matches schema.
- **Telegram integration**: currently marked as not implemented yet.

## License

No license file is currently included in this repository.
