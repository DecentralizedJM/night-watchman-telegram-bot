# Night Watchman 🌙

24/7 Telegram watchdog & moderation bot. Protects your groups from spam, scams, bad language, and more.

**Latest Release:** v1.1.4 (December 11, 2025) - 🐛 Bug Fixes & Memory Management
- **FIXED:** `/rep` command in DM no longer falsely claims everyone is an admin
- **FIXED:** Memory leaks - added periodic cleanup for in-memory caches
- **IMPROVED:** Test suite restructured into `tests/` directory
- Automatic cache cleanup every 30 minutes (message_authors, enhanced_messages, etc.)
- Prevents unbounded memory growth on long-running instances

**Previous Release:** v1.1.3 (December 10, 2025) - 🔗 Hyperlink + Emoji Detection
- **NEW RULE:** Messages with hyperlinked text (text_link) + more than 2 emojis = instant ban
- Catches disguised spam links hidden behind pretty emoji-laden text
- Improved emoji detection pattern for better coverage

**Previous Release:** v1.1.2 (December 10, 2025) - 📤 Forwarded Spam Detection Fix
- **CRITICAL FIX:** Forwarded messages now analyzed for spam content before taking action
- Forwarded casino/bot spam now triggers instant ban (not just mute)
- Added new instant-ban keywords: "winning streak", "top prize", "telegram bonus", etc.

**Previous Release:** v1.1.1 (December 9, 2025) - 🛡️ Aggressive Anti-Spam Overhaul
- Fixed all 6 reported scammer detection failures
- Cyrillic character deobfuscation for porn spam
- Instant-ban system for zero-tolerance violations
- Forward violation tracking with escalating penalties
- Bot account blocking
- Cool sassy ban message templates

## Features

### 🛡️ Core Protection
- **Real-time spam detection** using multiple signals
- **CAS integration** - checks users against Combot Anti-Spam database (1M+ groups)
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

## 🚀 Recent Updates (v1.1.4)

### � Bug Fixes
- **`/rep` in DM fixed** - No longer shows "You're an admin!" to everyone
- In DM context, `/rep` now correctly shows your actual reputation

### 🧹 Memory Management
- Added `_cleanup_caches()` method for periodic memory cleanup
- Runs automatically every 30 minutes during normal operation
- Prevents unbounded growth of in-memory dictionaries:
  - `message_authors` - capped at 5,000 entries
  - `enhanced_messages` - capped at 2,000 entries
  - `report_cooldowns` - expired entries removed
  - `media_timestamps` - entries older than 1 hour removed
  - `member_join_dates` - entries older than 7 days removed

### 🧪 Testing Improvements
- Restructured tests into `tests/` directory
- Added pytest-compatible test functions
- Run tests with: `python tests/test_spam_detection.py`

## Previous Updates (v1.1.3)

### � Hyperlink + Emoji Detection
**Problem:** Spammers were hiding malicious links behind pretty emoji-laden text.

**Fix:** Messages with hyperlinked text (text_link entity) + more than 2 emojis now trigger instant ban.

## Previous Updates (v1.1.2)

### 🎯 Fixed All 6 Scammer Detection Failures
1. **Cyrillic-obfuscated porn** - Deobfuscates Cyrillic lookalikes (х→x, р→p, о→o)
2. **Aggressive DM solicitation** - Detects "DM me now", "inbox me"
3. **Emoji-obfuscated links** - Flags excessive emojis + bot links
4. **Bot account joins** - Blocks accounts by is_bot flag + username patterns
5. **Casino/betting promo** - Instant bans on 1win, casino keywords
6. **Forwarded spam** - Mutes on first, bans on repeat

### 💥 Instant-Ban System
Zero-tolerance violations trigger immediate permanent ban:
- Adult/porn content (normalized for obfuscation)
- Telegram bot links (t.me/botname)
- DM solicitation phrases
- Casino & betting scams
- Excessive emoji spam combinations

### 🎭 Cool Ban Messages
Bot now responds with entertaining ban notifications across 8 categories with sassy responses.

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
| `/enhance` | Award +15 reputation points (reply to message) |
| `/cas` | Check user against CAS anti-spam database |
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
| Daily activity | +5 |
| Valid spam report | +10 |
| 7-day streak bonus | +5 |
| 30-day streak bonus | +10 |
| Admin enhancement (`/enhance`) | +15 |
| Warning received | -10 |
| Muted | -25 |
| Unmuted (false positive) | +15 |

### Levels (Display Only)
| Level | Points | Description |
|-------|--------|-------------|
| 🆕 Newcomer | 0-50 | New to the community |
| 🌟 Member | 51-200 | Active participant |
| ⭐ Trusted | 201-500 | Regular contributor |
| 💎 VIP | 501+ | Top community member |

> **Note:** Levels are for display/recognition only. All moderation rules apply equally to everyone except admins.

---

*Built with ❤️ by @DecentralizedJM | Powered by Mudrex*
