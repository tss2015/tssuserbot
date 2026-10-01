# Telegram Userbot Hosting Manager — Enhanced

Production-oriented modular baseline for managing a user's own Telegram account and running authorized group-management tasks.

## Included features

### Account management
- `/start` control panel
- `/Logsession` encrypted StringSession login
- Account status
- Logout with confirmation
- Automatic session reconnect after process rotation/restart
- Per-user client isolation

### Task system
- `/tagall`
- Preview/confirmation before starting
- Per-user task lock
- Configurable delay
- Configurable batch size
- Maximum member limit
- Persistent task records
- Progress updates
- `/cancel`
- FloodWait detection
- RPC error accounting
- Task history

### Settings
- `/settings`
- Per-user delay controls
- Per-user batch-size controls
- Global safety minimum delay

### Administration
- `/admin`
- `/stats`
- `/users`
- `/tasks`
- Maintenance status
- Broadcast intentionally disabled by default

### Reliability
- Async architecture
- Graceful shutdown
- Session reconnect
- Health endpoint
- MongoDB indexes
- GitHub CI
- GitHub 5-hour rotation workflow
- Ubuntu systemd service

### Security
- Fernet encryption for stored sessions
- No OTP/2FA persistence
- Environment-based secrets
- `.env` ignored
- Per-user authorization
- Secret-scan CI job
- No anti-spam bypass
- Telegram FloodWait is respected

## Environment

See `.env.example`.

Generate the session encryption key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Testing

```bash
python -m compileall -q .
ruff check .
pytest -q
```

## GitHub

Use `.github/workflows/ci.yml` for validation.

Use `.github/workflows/rotation.yml` only for temporary runner rotation. GitHub Actions runners are ephemeral; a VPS/systemd deployment is preferable for continuous production service.

## VPS

Install dependencies and use:

```bash
sudo cp deploy/telegram-userbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-userbot
```

## Safety

This project intentionally does not implement techniques intended to bypass Telegram anti-spam, rate limits, FloodWait, or account restrictions.


## Mood & Engagement System

The bot now has five moods:

- `happy`
- `sassy`
- `sulky`
- `romantic`
- `sleepy`

Commands:

```text
/mood
/setmood sassy
/randommood
/game
/gm
/gn
```

`/setmood` and `/randommood` are admin-only.

The mood can influence tagging completion/cancellation messages and engagement messages.

### Scheduled messages

Set:

```env
ENABLE_SCHEDULED_MESSAGES=true
```

Scheduled destinations must be explicitly configured in MongoDB under `scheduled_chats`. The scheduler does not discover or message arbitrary groups.

This keeps automated messaging opt-in rather than sending unsolicited messages to every connected group.

## AI Mood Tagging

Groq AI is enabled by default for `/tgall` message generation when `GROQ_API_KEY` is configured.
The five explicit mood commands are:

```text
/tgallhappy [optional instruction]
/tgallsassy [optional instruction]
/tgallsulky [optional instruction]
/tgallromantic [optional instruction]
/tgallsleepy [optional instruction]
```

The normal `/tgall` command uses the current chat mood. You can also write:

```text
/tgall romantic kha kho gye ho sab
```

The custom instruction is passed to Groq as context and the generated message is sent before the mention list.

### Per-user Telegram account isolation

The Telegram bot is only the control interface. The actual tagging message is sent by the **same Telegram user account that issued the command**, using that user's connected Telethon session.

For example:

```text
Deepak -> /tgallhappy -> Deepak's Telegram account sends the tag
Lucky  -> /tgallsassy -> Lucky's Telegram account sends the tag
```

If the requester has no connected userbot session, the bot sends a private login-required message and does not use another person's session.

Only group administrators may start a tagging task.

### Login methods

```text
/lognum
/logsession
```

`/logsession` accepts an existing authorized Telethon StringSession. `/lognum` starts the phone-login flow. OTP and 2FA secrets are never persisted.

### Groq configuration

```env
GROQ_API_KEY=your_key
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_TIMEOUT=20
```

If the Groq API is temporarily unavailable, the bot uses a local mood fallback instead of exposing credentials or stopping the tagging task setup.
