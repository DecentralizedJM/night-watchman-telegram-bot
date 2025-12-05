# Night Watchman 🌙

Telegram spam detection & moderation bot. Protects your groups 24/7.

## Features

- **Real-time spam detection** using multiple signals
- **Auto-delete** spam messages
- **Warn/mute** repeat offenders
- **New user restrictions** - blocks links from users < 24h in group
- **Rate limiting** - detects message floods
- **Admin reports** - sends spam alerts to you

## Spam Detection Signals

| Signal | Description |
|--------|-------------|
| Keywords | Detects scam phrases ("dm me for gains", "guaranteed profit") |
| URLs | Blocks suspicious links, URL shorteners |
| New users | Restricts link posting for new members |
| Rate limit | Flags users sending too many messages |
| Duplicates | Detects repeated spam messages |
| Formatting | Catches excessive CAPS, emojis |
| Crypto addresses | Flags wallet addresses (often scams) |

## Setup

1. Create a bot with @BotFather
2. Copy `.env.example` to `.env` and add your token
3. Add the bot to your group **as admin** with delete permissions

```bash
pip install -r requirements.txt
python3 night_watchman.py
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `ADMIN_CHAT_ID` | Your chat ID for spam reports |

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message (DM) |
| `/stats` | Show bot statistics (DM) |

## Required Bot Permissions

The bot needs these admin permissions in the group:
- Delete messages
- Restrict members (for muting)

## Actions

| Spam Score | Action |
|------------|--------|
| ≥ 0.7 | Delete + Warn user |
| ≥ 0.5 | Delete only |
| ≥ 0.3 | Flag for review |
| < 0.3 | Allow |

After 3 warnings, user is muted for 24 hours.

---

*Built with ❤️ by @DecentralizedJM | Powered by Mudrex*
