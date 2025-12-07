"""
Night Watchman Bot Configuration
Telegram Spam Detection & Moderation
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Telegram Settings
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # Where to send spam reports
    
    # Spam Detection Settings
    SPAM_KEYWORDS = [
        # Crypto scams
        "dm me for", "dm for gains", "100x", "guaranteed profit",
        "free airdrop", "claim now", "act fast", "limited time",
        "wallet connect", "validate wallet", "sync wallet",
        # Common spam patterns
        "click here", "join now", "hurry up", "don't miss",
        "make money fast", "work from home", "be your own boss",
        # Suspicious phrases
        "send me", "invest with me", "trading signals",
        "binary options", "forex signals",
    ]
    
    # Suspicious URL patterns
    SUSPICIOUS_DOMAINS = [
        "bit.ly", "tinyurl", "t.co", "goo.gl",  # URL shorteners (often abused)
        "telegram.me", "t.me",  # External telegram links
        # Add known scam domains
    ]
    
    # Whitelisted domains (always allowed)
    WHITELISTED_DOMAINS = [
        "mudrex.com",
        "binance.com",
        "bybit.com",
        "coingecko.com",
        "coinmarketcap.com",
        "tradingview.com",
        "github.com",
    ]
    
    # New user settings
    NEW_USER_LINK_BLOCK_HOURS = 24  # Block links from users < 24h in group
    NEW_USER_WARNING_THRESHOLD = 2  # Warnings before mute
    
    # Rate limiting
    MAX_MESSAGES_PER_MINUTE = 10  # Flag users sending too fast
    DUPLICATE_MESSAGE_THRESHOLD = 3  # Same message X times = spam
    
    # Actions
    AUTO_DELETE_SPAM = True
    AUTO_WARN_USER = True
    AUTO_MUTE_AFTER_WARNINGS = 3
    AUTO_BAN_AFTER_WARNINGS = 5  # Ban after X warnings
    MUTE_DURATION_HOURS = 24
    
    # Bad Language Detection
    BAD_LANGUAGE_ENABLED = True
    BAD_LANGUAGE_WORDS = [
        # Profanity (common words - add more as needed)
        "fuck", "shit", "damn", "bitch", "asshole", "bastard",
        "crap", "piss", "hell", "dick", "cock", "pussy",
        # Add more as needed - keep it configurable
    ]
    BAD_LANGUAGE_ACTION = "delete_and_warn"  # "warn", "delete", "delete_and_warn", "mute"
    
    # New User Verification
    VERIFY_NEW_USERS = True
    MIN_ACCOUNT_AGE_DAYS = 7  # Require account to be at least 7 days old
    SUSPICIOUS_USERNAME_PATTERNS = [
        r'^[0-9]+$',  # Only numbers
        r'^user[0-9]+$',  # user12345 pattern
        r'^telegram[0-9]+$',  # telegram123 pattern
        r'.*spam.*',  # Contains "spam"
        r'.*scam.*',  # Contains "scam"
    ]
    AUTO_BAN_SUSPICIOUS_JOINS = False  # Auto-ban or just restrict
    RESTRICT_NEW_USERS_HOURS = 24  # Restrict new users for X hours
    
    # Anti-Raid Protection
    ANTI_RAID_ENABLED = True
    RAID_DETECTION_WINDOW_MINUTES = 5  # Check last 5 minutes
    RAID_THRESHOLD_USERS = 10  # If 10+ new users join in window, it's a raid
    
    # Welcome Message
    SEND_WELCOME_MESSAGE = True
    WELCOME_MESSAGE = """👋 Welcome to the group!

📋 <b>Rules:</b>
• No spam or scams
• No bad language
• Be respectful
• No advertising without permission

⚠️ Violations will result in warnings, mutes, or bans."""
    
    # Non-Indian Language Detection
    BLOCK_NON_INDIAN_LANGUAGES = True
    NON_INDIAN_LANGUAGES = [
        'chinese', 'korean', 'russian', 'japanese', 'arabic', 'thai', 'vietnamese'
    ]
    AUTO_BAN_NON_INDIAN_SPAM = True  # Auto-ban if non-Indian language + suspicious content
    
    # Bot Message Auto-Delete
    AUTO_DELETE_BOT_MESSAGES = True
    BOT_MESSAGE_DELETE_DELAY_SECONDS = 60  # Delete after 1 minute
    
    # Admin Commands
    ADMIN_COMMANDS_ENABLED = True
    
    # Admin User IDs (can access /analytics via DM)
    # Add your Telegram user ID here
    ADMIN_USER_IDS = [
        int(x) for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip()
    ] if os.getenv("ADMIN_USER_IDS") else [395803228]  # Default: @DecentralizedJM
    
    # Analytics Settings
    ANALYTICS_ENABLED = True
    ANALYTICS_RETENTION_DAYS = 90  # Keep data for 90 days
    ANALYTICS_DATA_DIR = os.getenv("ANALYTICS_DATA_DIR", "data")  # Configurable for Railway volumes
    
    # ==================== NEW FEATURES ====================
    
    # Custom Commands
    GUIDELINES_MESSAGE = """📋 <b>Community Guidelines</b>

1️⃣ <b>Be Respectful</b>
   • Treat everyone with respect
   • No harassment or bullying
   • No discrimination

2️⃣ <b>No Spam or Scams</b>
   • No unsolicited promotions
   • No phishing or scam links
   • No fake giveaways

3️⃣ <b>Stay On Topic</b>
   • Keep discussions relevant to trading/crypto
   • Use appropriate channels

4️⃣ <b>No Bad Language</b>
   • Keep it professional
   • No excessive profanity

5️⃣ <b>No Shilling</b>
   • No promoting other projects without permission

⚠️ Violations result in warnings, mutes, or bans.

<i>Powered by Mudrex</i>"""
    
    HELP_MESSAGE = """🌙 <b>Night Watchman Commands</b>

<b>Everyone:</b>
/guidelines - Community rules
/help - This message
/admins - Tag admins for help
/report - Report spam (reply to message)
/rep - Check your reputation
/leaderboard - Top users

<b>Admins:</b>
/warn - Warn a user
/mute - Mute a user
/ban - Ban a user
/unwarn - Clear warnings
/stats - Bot statistics
/analytics - Group analytics (DM)

<i>Powered by Mudrex</i>"""
    
    # Reputation System
    REPUTATION_ENABLED = True
    REP_DAILY_ACTIVE = 1        # Points for daily activity
    REP_VALID_REPORT = 10       # Points for valid spam report
    REP_WARNING_PENALTY = 10    # Points lost for warning
    REP_MUTE_PENALTY = 25       # Points lost for mute
    REP_UNMUTE_BONUS = 15       # Points for being unmuted (false positive)
    
    # Reputation Levels
    REP_LEVEL_MEMBER = 50       # Can post links
    REP_LEVEL_TRUSTED = 200     # Bypass some restrictions
    REP_LEVEL_VIP = 500         # Can forward messages
    
    # Forward Detection
    BLOCK_FORWARDS = True
    FORWARD_ALLOW_ADMINS = True
    FORWARD_MIN_REP = 500       # VIPs can forward (REP_LEVEL_VIP)
    
    # Username Requirement
    REQUIRE_USERNAME = True
    USERNAME_GRACE_PERIOD_HOURS = 24  # Hours before kick
    USERNAME_WARNING_MESSAGE = """⚠️ <b>Username Required</b>

Please set a Telegram username to participate in this group.

Go to Settings → Username to set one.

You have 24 hours before being removed."""
    
    # Report System
    REPORT_ENABLED = True
    REPORT_COOLDOWN_SECONDS = 60  # Prevent report spam
    
    # Logging
    LOG_FILE = "logs/night_watchman.log"
    LOG_LEVEL = "INFO"
