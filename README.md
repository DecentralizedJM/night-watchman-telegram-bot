# Night Watchman 🌙

24/7 Telegram watchdog & moderation bot. Protects your groups from spam, scams, bad language, and more.

## Features

### 🛡️ Core Protection
- **Real-time spam detection** using multiple signals
- **Bad language detection** - automatically detects and warns about profanity
- **Scammer detection** - identifies suspicious accounts on join
- **Anti-raid protection** - detects coordinated attacks
- **Auto-delete** spam/bad language messages
- **Warn/mute/ban** repeat offenders automatically

### 👥 User Management
- **New user verification** - checks for suspicious account patterns
- **New user restrictions** - blocks links/media from users < 24h in group
- **Welcome messages** - greets new members with rules
- **Rate limiting** - detects message floods
- **Duplicate detection** - catches repeated spam messages

### 🔧 Admin Tools
- **Admin commands** - `/warn`, `/ban`, `/mute`, `/stats`, `/unwarn`
- **Admin reports** - sends alerts to your chat
- **Statistics tracking** - monitor bot activity

## Detection Signals

| Signal | Description |
|--------|-------------|
| **Spam Keywords** | Detects scam phrases ("dm me for gains", "guaranteed profit") |
| **Bad Language** | Detects profanity and inappropriate words |
| **URLs** | Blocks suspicious links, URL shorteners |
| **New Users** | Restricts link posting for new members |
| **Suspicious Accounts** | Detects suspicious usernames, missing profiles |
| **Rate Limit** | Flags users sending too many messages |
| **Duplicates** | Detects repeated spam messages |
| **Formatting** | Catches excessive CAPS, emojis |
| **Crypto Addresses** | Flags wallet addresses (often scams) |
| **Raid Detection** | Detects multiple users joining quickly |

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
| `ADMIN_USER_IDS` | Comma-separated list of admin user IDs for /analytics |

## Commands

### User Commands (Private Chat)
| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/stats` | Show bot statistics |

### Admin Commands (In Group - Reply to User)
| Command | Description |
|---------|-------------|
| `/warn` | Warn a user (reply to their message) |
| `/ban` | Ban a user permanently |
| `/mute` | Mute a user for 24 hours |
| `/unwarn` | Clear warnings for a user |
| `/stats` | Show detailed bot statistics |

### Analytics Commands (Admin Only - Private)
| Command | Description |
|---------|-------------|
| `/analytics` | Today's group analytics |
| `/analytics 7d` | Last 7 days summary |
| `/analytics 14d` | Last 14 days summary |
| `/analytics 30d` | Last 30 days summary |
| `/analytics week` | Same as 7d |
| `/analytics month` | Same as 30d |

> **Note:** Analytics commands can be used in the group (command is deleted, results sent via DM) or in private chat with the bot.

## Analytics Features

📊 **What's tracked:**
- 👥 Member joins/exits per day
- 💬 Total messages per day
- 🚫 Spam blocked per day
- 🤬 Bad language detected
- ⚠️ Warnings issued
- 🔇 Users muted
- 🔨 Users banned
- 🚨 Raid alerts
- 👤 Active users per day
- ⏰ Peak activity hours

## Required Bot Permissions

The bot needs these admin permissions in the group:
- Delete messages
- Restrict members (for muting)

## Auto-Moderation Actions

### Spam Detection
| Spam Score | Action |
|------------|--------|
| ≥ 0.7 | Delete + Warn user |
| ≥ 0.5 | Delete only |
| ≥ 0.3 | Flag for review |
| < 0.3 | Allow |

### Warning System
- **3 warnings** → User is muted for 24 hours
- **5 warnings** → User is banned permanently

### Bad Language
- Configurable action: `warn`, `delete`, `delete_and_warn`, or `mute`
- Default: Warns user and deletes message

### New User Protection
- Links blocked for first 24 hours
- Suspicious accounts can be auto-banned or restricted
- Anti-raid protection activates if 10+ users join in 5 minutes

---

*Built with ❤️ by @DecentralizedJM | Powered by Mudrex*
