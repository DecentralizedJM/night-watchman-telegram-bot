# 🌙 Night Watchman Bot - Full Specification

## Overview
24/7 Telegram watchdog & moderation bot that automatically protects groups from spam, scams, bad language, and malicious users.

---

## 🛡️ Core Protection Features

### 1. Spam Detection (Multi-Signal Analysis)
- **Keyword Detection**: Detects scam phrases and spam patterns
  - Crypto scams: "dm me for gains", "100x", "guaranteed profit", "free airdrop"
  - Common spam: "click here", "join now", "hurry up", "make money fast"
  - Suspicious phrases: "send me", "invest with me", "trading signals"
  
- **URL Analysis**: 
  - Blocks suspicious domains (URL shorteners: bit.ly, tinyurl, t.co)
  - Whitelists trusted domains (mudrex.com, binance.com, github.com, etc.)
  - Detects external Telegram links (t.me, telegram.me)
  
- **Mention Spam Detection**: ⭐ NEW
  - Detects repeated @mentions with promotional content
  - Pattern: "@channel @channel @channel" + "Join now" + link
  - Scoring:
    * 5+ mentions: 0.7 spam score (high confidence)
    * 3-4 mentions + promotional keywords: 0.6 spam score
    * 2+ duplicate mentions: flagged as spam
  - Catches bot spam like:
    ```
    @trading @profits @crypto
    Join now at [link]
    ```

- **Crypto Address Detection**: Flags wallet addresses (ETH, BTC, SOL)
- **Duplicate Message Detection**: Catches repeated spam messages
- **Formatting Abuse**: Detects excessive CAPS, repeated characters, too many emojis
- **Rate Limiting**: Flags users sending >10 messages per minute

**Spam Scoring System:**
- Score ≥ 0.7 → Delete + Warn user
- Score ≥ 0.5 → Delete only
- Score ≥ 0.3 → Flag for review
- Score < 0.3 → Allow

### 2. Bad Language Detection (English + Hindi/Hinglish)
- **Profanity Filter**: Detects inappropriate words in multiple languages
  - **English profanity**: fuck, shit, bitch, etc.
  - **Hindi/Hinglish abuse**: madarchod, bhenchod, chutiya, gaandu, etc.
  - **Romanized variations**: mc, bc, bkl, etc.
- **Configurable Actions**:
  - `warn` - Warn user only
  - `delete` - Delete message only
  - `delete_and_warn` - Delete + Warn (default)
  - `mute` - Direct mute
- **Auto-escalation**: After warnings, mutes/bans apply

### 3. Hindi/Hinglish Spam Detection
- **Detects Hindi spam patterns**: "dm karo", "paisa kamao", "lakho kamao"
- **Crypto scams in Hinglish**: "free crypto milega", "airdrop milega"
- **Action phrases**: "whatsapp karo", "link pe click", "jaldi grab karo"
- **All Indian languages allowed**: Hindi (Devanagari), Tamil, Telugu, Bengali, etc.

### 4. Non-Indian Language Detection & Auto-Delete/Ban
- **Detects Languages**: Chinese, Korean, Russian, Japanese, Arabic, Thai, Vietnamese
- **Allows All Indian Languages**: Hindi, Tamil, Telugu, Bengali, Gujarati, etc.
- **Always Deletes**: All messages in non-Indian languages are immediately deleted
- **Immediate Ban**: Users posting links/URLs in non-Indian languages are banned instantly
- **Warning Only**: Messages without links trigger deletion and warning (no ban)
- **Admin Notification**: Reports sent to admin chat for all foreign language detections

### 5. Scammer Detection on Join
- **Suspicious Username Patterns**:
  - Only numbers (12345)
  - Generic patterns (user123, telegram123)
  - Contains "spam" or "scam"
- **Missing Profile Info**: Flags accounts with no username/name
- **Auto-Actions**: Can auto-ban or restrict suspicious accounts
- **New User Restrictions**: Blocks links/media for first 24 hours

### 5. Anti-Raid Protection
- **Raid Detection**: Detects when 10+ users join within 5 minutes
- **Admin Alerts**: Notifies admins of potential coordinated attacks
- **Configurable Thresholds**: Adjustable window and user count

### 6. CAS (Combot Anti-Spam) Integration
- **Global Spam Database**: Checks new members against CAS database
- **Auto-Ban Known Spammers**: Instantly bans users flagged across 1M+ groups
- **Manual Checks**: `/cas @user` command to check any user
- **Admin Notifications**: Reports when CAS-banned users try to join
- **API**: Uses free public CAS API (api.cas.chat)

### 7. Flood Detection
- **Message Rate Limiting**: Flags users sending too many messages
- **Duplicate Detection**: Catches spam floods with same message
- **Automatic Action**: Warns/mutes based on severity

---

## ⚙️ Automatic Moderation Actions

### Warning System
1. **1st Violation** → Warning + Message deleted
2. **2nd Violation** → Warning + Message deleted
3. **3rd Warning** → Auto-mute for 24 hours
4. **5th Warning** → Auto-ban permanently

### Message Actions
- **Auto-delete spam**: Enabled by default
- **Auto-delete bad language**: Configurable
- **Auto-warn users**: Enabled by default
- **Bot message auto-delete**: All bot messages deleted after 60 seconds

### User Actions
- **Mute**: Restricts user from sending messages for 24 hours
- **Ban**: Permanent ban from group
- **Restrict**: New users restricted (no links/media) for 24 hours

---

## 👥 User Management

### New User Protection
- **Link Blocking**: New users (<24h) cannot post links
- **Media Restrictions**: New users restricted from posting media
- **Verification**: Checks for suspicious account patterns
- **Welcome Messages**: Automatic greeting with group rules

### User Tracking
- **Join Date Tracking**: Tracks when users joined
- **Warning History**: Maintains warning count per user
- **Activity Tracking**: Monitors user message patterns

---

## 🔧 Admin Commands

### In-Group Commands (Reply to User, @username, or User ID)
| Command | Description | Usage |
|---------|-------------|-------|
| `/warn` | Warn a user | Reply to message, `/warn @username`, or `/warn <user_id>` |
| `/ban` | Ban user permanently | Reply, `/ban @username`, or `/ban <user_id>` |
| `/mute` | Mute user for 24h | Reply, `/mute @username`, or `/mute <user_id>` |
| `/unwarn` | Clear user warnings | Reply, `/unwarn @username`, or `/unwarn <user_id>` |
| `/cas` | Check user against CAS database | Reply, `/cas @username`, or `/cas <user_id>` |
| `/enhance` | Award +15 reputation points | Reply with `/enhance` (auto-deletes in 1 min) |
| `/stats` | Show bot statistics | Use `/stats` in group |

> **Note**: When using `@username`, the user must be mentioned (Telegram will auto-complete). User ID can be found in bot notifications when a user is warned/muted. Useful when the original message was deleted.

### Private Chat Commands
| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/stats` | Bot statistics |
| `/analytics` | Today's analytics (admin only) |
| `/analytics 7d` | Last 7 days (admin only) |
| `/analytics 14d` | Last 14 days (admin only) |
| `/analytics 30d` | Last 30 days (admin only) |
| `/analytics week` | Same as 7d (admin only) |
| `/analytics month` | Same as 30d (admin only) |

**Note**: Analytics commands can be used in group (command auto-deleted, results sent via DM) or in private chat.

---

## 📊 Analytics & Reporting

### Tracked Metrics
- **Member Activity**:
  - New Active Members (first-time message senders)
  - Total Known Users (all users who ever messaged)
  - Active users per day
  
- **Message Activity**:
  - Total messages per day
  - Messages per hour (peak hours analysis)
  
- **Moderation Activity**:
  - Spam blocked per day
  - Bad language detected
  - Warnings issued
  - Users muted
  - Users banned
  - Raid alerts
  
- **Time Analysis**:
  - Peak activity hours (UTC)
  - Daily trends
  - Weekly/monthly summaries

> **Note**: For groups with hidden member lists, Telegram doesn't send join/exit notifications to bots. Instead, we track "New Active Members" - users who send their first message in the group. This is more useful as it tracks engaged members, not just people who joined and lurked.

### Data Storage
- **File**: `data/analytics.json`
- **Retention**: 90 days (configurable)
- **Format**: JSON with daily and hourly breakdowns

### Analytics Features
- **Timeframe Options**: today, 7d, 14d, 30d, week, month
- **Peak Hours**: Shows top 3 busiest hours for weekly reports
- **Private Delivery**: Results sent via DM (command deleted from group)
- **All Admins**: Any group admin can use `/analytics` (not just ADMIN_USER_IDS)

---

## 🔔 Admin Notifications

### Spam Reports
Sent to `ADMIN_CHAT_ID` when spam is detected:
- User information (name, username, ID)
- Chat ID
- Message content (truncated)
- Detection reasons
- Spam score
- Action taken

### Bad Language Reports
- User details
- Detected words
- Message content
- Action taken

### Non-Indian Language Spam
- User details
- Detected language
- Message content
- Action taken:
  - With links: Immediate ban
  - Without links: Delete and warn only

### Raid Alerts
- Chat ID
- Number of users joined
- Time window
- Alert level

### Suspicious User Alerts
- User details
- Suspicious patterns detected
- Action taken (ban/restrict)

### User Reports
- Reporter information
- Reported user details
- Reported message content
- Chat and message ID for action

---

## ⭐ Reputation System

### Points System (No Perks - Campaign Ready)
Points track engagement and can be used for campaigns/rewards. **No restrictions based on reputation.**

| Action | Points | Direction |
|--------|--------|-----------|
| Daily activity | +5 | Positive |
| Valid spam report | +10 | Positive |
| 7-day active streak bonus | +5 | Positive |
| 30-day active streak bonus | +10 | Positive |
| Admin enhancement (`/enhance`) | +15 | Positive |
| Warning received | -10 | Negative |
| Muted | -25 | Negative |
| Unmuted (false positive) | +15 | Positive |

**Admin Enhancement:**
- Admins use `/enhance` command by replying to quality messages (+15 points)
- Command and confirmation auto-delete after 1 minute (keeps chat clean)
- Admins are excluded from earning reputation points
- Cannot enhance other admins

### Reputation Levels (Display Only)
| Level | Points | Emoji |
|-------|--------|-------|
| Newcomer | 0-50 | 🆕 |
| Member | 51-200 | 🌟 |
| Trusted | 201-500 | ⭐ |
| VIP | 501+ | 💎 |

**Note:** Levels are for display only. No perks or restrictions are applied.

### Commands
- `/rep` - Check your reputation and level
- `/leaderboard` - All-time top 10 users
- `/leaderboard 7` - Top users from last 7 days
- `/leaderboard 30` - Top users from last 30 days

### Data Storage
- **File**: `data/reputation.json`
- **Tracked**: Points, daily points, warnings, valid reports, join date, last active

---

## 💬 User Commands

| Command | Description | Available To |
|---------|-------------|--------------|
| `/guidelines` | Show community rules | Everyone |
| `/help` | List all commands | Everyone |
| `/admins` | Tag all group admins | Everyone |
| `/report` | Report spam (reply to message) | Everyone |
| `/rep` | Check your reputation | Everyone |
| `/leaderboard` | All-time top 10 users | Everyone |
| `/leaderboard N` | Top users from last N days | Everyone |

---

## ↩️ Forward Detection

### How It Works
- **Blocks all forwarded messages** by default
- Detects: `forward_from`, `forward_from_chat`, `forward_date`
- **Only admins can forward** (configurable)

### Configuration
```python
BLOCK_FORWARDS = True
FORWARD_ALLOW_ADMINS = True
# No VIP bypass - forwards blocked for everyone except admins
```

---

## 📛 Username Requirement

### How It Works
1. User joins without Telegram username
2. Bot immediately mutes user
3. Warning message with instructions sent
4. 24-hour grace period to set username
5. User kicked if no username after grace period

### Configuration
```python
REQUIRE_USERNAME = True
USERNAME_GRACE_PERIOD_HOURS = 24
USERNAME_WARNING_MESSAGE = "..."  # Customizable
```

---

## 🚨 Report System

### How It Works
1. User replies to suspicious message with `/report`
2. Report command is deleted (keeps chat clean)
3. Report sent to admin chat with:
   - Reporter info
   - Reported user info
   - Message content
   - Chat/message IDs for action
4. Reporter gets confirmation

### Anti-Abuse
- **Cooldown**: 60 seconds between reports per user
- **Valid reports**: Earn +10 reputation points

### Configuration
```python
REPORT_ENABLED = True
REPORT_COOLDOWN_SECONDS = 60
```

---

## ⚙️ Configuration Options

### Spam Detection
```python
SPAM_KEYWORDS = [...]  # Customizable spam keywords
SUSPICIOUS_DOMAINS = [...]  # Blocked domains
WHITELISTED_DOMAINS = [...]  # Always allowed
MAX_MESSAGES_PER_MINUTE = 10
DUPLICATE_MESSAGE_THRESHOLD = 3
```

### Bad Language
```python
BAD_LANGUAGE_ENABLED = True
BAD_LANGUAGE_WORDS = [...]  # Customizable word list
BAD_LANGUAGE_ACTION = "delete_and_warn"  # warn/delete/delete_and_warn/mute
```

### New User Protection
```python
VERIFY_NEW_USERS = True
NEW_USER_LINK_BLOCK_HOURS = 24
RESTRICT_NEW_USERS_HOURS = 24
AUTO_BAN_SUSPICIOUS_JOINS = False
SUSPICIOUS_USERNAME_PATTERNS = [...]
```

### Anti-Raid
```python
ANTI_RAID_ENABLED = True
RAID_DETECTION_WINDOW_MINUTES = 5
RAID_THRESHOLD_USERS = 10
```

### Non-Indian Language
```python
BLOCK_NON_INDIAN_LANGUAGES = True
AUTO_BAN_NON_INDIAN_SPAM = True
NON_INDIAN_LANGUAGES = ['chinese', 'korean', 'russian', ...]
```

### Auto-Moderation
```python
AUTO_DELETE_SPAM = True
AUTO_WARN_USER = True
AUTO_MUTE_AFTER_WARNINGS = 3
AUTO_BAN_AFTER_WARNINGS = 5
MUTE_DURATION_HOURS = 24
```

### Bot Messages
```python
AUTO_DELETE_BOT_MESSAGES = True
BOT_MESSAGE_DELETE_DELAY_SECONDS = 60
```

### Analytics
```python
ANALYTICS_ENABLED = True
ANALYTICS_RETENTION_DAYS = 90
ADMIN_USER_IDS = [...]  # List of admin user IDs
```

### Welcome Messages
```python
SEND_WELCOME_MESSAGE = True
WELCOME_MESSAGE = "..."  # Customizable
```

---

## 🔐 Security & Permissions

### Required Bot Permissions
- **Delete Messages**: Required for spam/bad language removal
- **Restrict Members**: Required for muting users
- **Ban Members**: Required for permanent bans

### Admin Access
- **ADMIN_CHAT_ID**: Receives spam reports and alerts
- **ADMIN_USER_IDS**: Can access `/analytics` command
- **Group Admins**: Can use moderation commands (`/warn`, `/ban`, `/mute`)

---

## 📁 File Structure

```
night-watchman-telegram-bot/
├── night_watchman.py      # Main bot file (1100+ lines)
├── spam_detector.py       # Spam detection engine
├── analytics_tracker.py   # Analytics tracking system
├── reputation_tracker.py  # Reputation system (NEW)
├── config.py             # Configuration settings
├── requirements.txt       # Python dependencies
├── README.md             # User documentation
├── FULL_SPEC.md          # This specification
├── data/
│   ├── analytics.json    # Analytics data (auto-created)
│   └── reputation.json   # Reputation data (auto-created)
└── logs/
    └── night_watchman.log # Bot logs (auto-created)
```

---

## 🚀 Technical Details

### Technology Stack
- **Language**: Python 3
- **HTTP Client**: httpx (async)
- **Data Storage**: JSON files
- **Logging**: Python logging module

### Performance
- **Async/Await**: Non-blocking operations
- **Connection Limits**: Max 10 connections, 5 keepalive
- **Timeout**: 35 seconds for polling, 10 seconds for API calls

### Data Persistence
- **Analytics**: Stored in `data/analytics.json`
- **In-Memory**: User warnings, join dates, message history
- **Retention**: 90 days for analytics data

---

## 📈 Statistics Tracked

### Real-time Stats
- Messages checked
- Spam detected
- Messages deleted
- Users warned
- Users muted
- Users banned
- Bad language detected
- Suspicious users detected
- Bot uptime

### Historical Analytics
- Daily joins/exits
- Daily messages
- Daily spam blocked
- Daily warnings/mutes/bans
- Active users per day
- Peak activity hours
- Raid alerts

---

## 🎯 Use Cases

1. **Crypto/Investment Groups**: Protects from scam links, fake airdrops, pump schemes
2. **Community Groups**: Maintains clean language and respectful environment
3. **International Groups**: Blocks non-local language spam
4. **High-Traffic Groups**: Handles floods and raids automatically
5. **Moderated Communities**: Provides 24/7 automated moderation

---

## 🔄 Update & Maintenance

### Regular Updates
- Spam keyword lists can be updated in `config.py`
- Bad language words can be customized
- Whitelisted domains can be added
- Suspicious patterns can be adjusted

### Monitoring
- Check logs in `logs/night_watchman.log`
- Review analytics via `/analytics` command
- Monitor admin notifications

---

## 📝 Environment Variables

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
ADMIN_CHAT_ID=your_chat_id_here
ADMIN_USER_IDS=123456789,987654321  # Optional, comma-separated
```

---

## ✅ Feature Checklist

- ✅ Real-time spam detection
- ✅ **Hindi/Hinglish spam detection**
- ✅ Bad language detection (English + Hindi)
- ✅ Non-Indian language blocking
- ✅ Scammer detection on join
- ✅ Anti-raid protection
- ✅ Auto-warn/mute/ban
- ✅ Admin commands
- ✅ Analytics tracking
- ✅ Admin notifications
- ✅ Welcome messages
- ✅ Bot message auto-delete
- ✅ New user restrictions
- ✅ Rate limiting
- ✅ Duplicate detection
- ✅ Crypto address detection
- ✅ URL filtering
- ✅ Peak hours analysis
- ✅ 90-day data retention
- ✅ **Reputation System** (points only, no perks)
- ✅ **Date-based Leaderboards** (/leaderboard N for last N days)
- ✅ **User Commands** (/guidelines, /help, /admins, /report, /rep, /leaderboard)
- ✅ **Forward Detection** (admins only)
- ✅ **Username Requirement** (mute on join, grace period)
- ✅ **Report System** (user reports to admins)

---

*Built with ❤️ by @DecentralizedJM | Powered by Mudrex*


