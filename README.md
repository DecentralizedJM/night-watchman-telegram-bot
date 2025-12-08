# Night Watchman 🌙

24/7 Telegram watchdog & moderation bot. Protects your groups from spam, scams, bad language, and more.

## Features

### 🛡️ Core Protection
- **Real-time spam detection** using multiple signals
- **Bad language detection** - automatically detects and warns about profanity
- **Scammer detection** - identifies suspicious accounts on join
- **Anti-raid protection** - detects coordinated attacks
- **Forward blocking** - prevents forwarded spam (VIPs exempt)
- **Auto-delete** spam/bad language messages
- **Warn/mute/ban** repeat offenders automatically

### 👥 User Management
- **New user verification** - checks for suspicious account patterns
- **New user restrictions** - blocks links/media from users < 24h in group
- **Username requirement** - mutes users without username, kicks after 24h
- **Welcome messages** - greets new members with rules
- **Rate limiting** - detects message floods
- **Duplicate detection** - catches repeated spam messages

### ⭐ Reputation System
- **Daily activity points** - +1 point per day active
- **Valid spam reports** - +10 points for helping moderate
- **Warning penalties** - -10 points per warning
- **Level progression**: Newcomer → Member → Trusted → VIP
- **VIP perks** - Can forward messages, bypass restrictions

### 🔧 Admin Tools
- **Admin commands** - `/warn`, `/ban`, `/mute`, `/stats`, `/unwarn`
- **Admin reports** - sends alerts to your chat
- **Statistics tracking** - monitor bot activity
- **Analytics** - detailed group analytics via DM

### 💬 User Commands
- `/guidelines` - Show community rules
- `/help` - List available commands
- `/admins` - Tag all admins for help
- `/report` - Report a message (reply to message)
- `/rep` - Check your reputation
- `/leaderboard` - Top 10 users by reputation

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

### Admin Commands (In Group - Reply, @username, or User ID)
| Command | Description |
|---------|-------------|
| `/warn` | Warn a user (reply, `/warn @user`, or `/warn <id>`) |
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

> **Note:** Analytics commands can be used by any group admin (command is deleted, results sent via DM) or in private chat with the bot.

## Analytics Features

📊 **What's tracked:**
- 🆕 New Active Members (first-time message senders)
- 👤 Total Known Users (all users who ever messaged)
- 💬 Total messages per day
- 🚫 Spam blocked per day
- 🤬 Bad language detected
- ⚠️ Warnings issued
- 🔇 Users muted
- 🔨 Users banned
- 🚨 Raid alerts
- 👤 Active users per day
- ⏰ Peak activity hours

> **Note:** For groups with hidden member lists, Telegram doesn't send join/exit notifications. Instead, we track "New Active Members" - users who send their first message.

## Required Bot Permissions

The bot needs these admin permissions in the group:
- Delete messages
- Restrict members (for muting)
- Add members (to receive member join/leave events)

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
- Username required - users without username are muted

## Reputation System

### Earning Points
| Action | Points |
|--------|--------|
| Daily activity | +1 |
| Valid spam report | +10 |
| Warning received | -10 |
| Muted | -25 |
| Unmuted (false positive) | +15 |

### Levels
| Level | Points | Perks |
|-------|--------|-------|
| 🆕 Newcomer | 0-50 | Standard restrictions |
| 🌟 Member | 51-200 | Can post links |
| ⭐ Trusted | 201-500 | Bypass some restrictions |
| 💎 VIP | 501+ | Can forward messages |

---

*Built with ❤️ by @DecentralizedJM | Powered by Mudrex*
