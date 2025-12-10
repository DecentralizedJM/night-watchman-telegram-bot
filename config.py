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
        # Crypto scams (English)
        "dm me for", "dm for gains", "100x", "guaranteed profit",
        "free airdrop", "claim now", "act fast", "limited time",
        "wallet connect", "validate wallet", "sync wallet",
        # Common spam patterns (English)
        "click here", "join now", "hurry up", "don't miss",
        "make money fast", "work from home", "be your own boss",
        # Suspicious phrases (English)
        "send me", "invest with me", "trading signals",
        "binary options", "forex signals",
        
        # AGGRESSIVE DM/CONTACT PATTERNS (INSTANT BAN)
        "dm me now", "dm me", "message me now", "message me",
        "inbox me now", "inbox me", "contact me now",
        "text me now", "text me", "pm me now", "pm me",
        "hit me up", "reach out now", "reach out to me",
        "slide into", "drop a dm", "send a dm",
        
        # Trading/Forex Scam Patterns
        "consistently profitable", "consistently profit",
        "straight months", "trading smart", "smart strategy",
        "trading emotionally", "level up your trading",
        "profitable for over", "profitable strategy",
        "proven strategy", "proven method", "proven system",
        
        # Casino/Betting Spam (INSTANT BAN)
        "big wins", "promo code", "welcome bonus", "1win",
        "casino", "betting", "jackpot", "slot", "roulette",
        "blackjack", "poker bonus", "free spins", "cash out",
        "win big", "massive win", "hit a win", "start cashing",
        "winning streak", "top prize", "grab bonus", "telegram bonus",
        "enter code", "heating up", "could be yours", "get bonus",
        "$200 free", "$100 free", "$500 free", "free $",
        
        # Adult/Porn (INSTANT BAN)
        "xxx", "porn", "p-o-r-n", "x x x", "p o r n",
        "onlyfans", "only fans", "18+", "adult content",
        "nudes", "sexy video", "hot video",
        
        # Hindi/Hinglish Spam Patterns
        "dm karo", "dm kijiye", "message karo", "contact karo",
        "inbox karo", "inbox me aao", "aaja inbox",
        "paisa kamao", "paise kamao", "ghar baithe kamao", "lakho kamao",
        "jaldi karo", "abhi join karo", "miss mat karo",
        "free mein", "muft mein", "guaranteed return",
        "double paisa", "paise double", "roz kamao", "daily kamao",
        "invest karo", "trading sikho", "profit pakka",
        "airdrop milega", "free crypto", "free coins",
        "whatsapp karo", "call karo", "telegram pe aao",
        "scheme join karo", "yahan click karo", "link pe click",
        "limited offer", "jaldi grab karo", "sirf aaj",
        "aaja dm", "dm kar", "inbox kar", "message kar",
    ]
    
    # INSTANT BAN keywords (no warnings, immediate ban)
    INSTANT_BAN_KEYWORDS = [
        # Adult/Porn
        "xxx", "porn", "p-o-r-n", "x x x", "p o r n",
        "onlyfans", "only fans", "nudes",
        # Casino/Betting
        "1win", "casino", "promo code", "welcome bonus",
        "big wins", "jackpot", "free spins",
        "winning streak", "top prize", "grab bonus", "telegram bonus",
        # Scam patterns
        "dm me now", "inbox me", "message me now",
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
        # English Profanity
        "fuck", "shit", "damn", "bitch", "asshole", "bastard",
        "crap", "piss", "hell", "dick", "cock", "pussy",
        
        # Hindi/Hinglish Profanity & Abuse
        "madarchod", "bhenchod", "chutiya", "gaandu", "haramkhor",
        "randi", "saala", "saali", "bhosdike", "lawda", "loda",
        "chut", "gand", "behenchod", "mc", "bc", "bkl",
        "kutte", "kutta", "kamina", "kamini", "harami",
        "chodu", "chodna", "chudai", "lund", "lundura",
        "jhant", "jhatu", "ullu", "gadha", "bakchod", "bakchodi",
        "madar", "behen", "bhosda", "bhosdika", "bhosdiwala",
        "tatti", "moot", "suvar", "suar", "hijda", "chakka",
        "dalla", "dallal", "rakhail", "pataka", "raand",
        
        # Hinglish variations (romanized)
        "madarc**d", "behen c**d", "chu***a", "g**du",
        "b***i", "r**di", "l**d", "bh**d",
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
    
    # Bot Account Blocking
    BLOCK_BOT_JOINS = True  # Auto-ban bot accounts that join
    BOT_USERNAME_PATTERNS = [
        r'.*bot$',  # Ends with "bot"
        r'.*_bot$',  # Ends with "_bot"
    ]
    
    # Anti-Raid Protection
    ANTI_RAID_ENABLED = True
    RAID_DETECTION_WINDOW_MINUTES = 5  # Check last 5 minutes
    RAID_THRESHOLD_USERS = 10  # If 10+ new users join in window, it's a raid
    
    # CAS (Combot Anti-Spam) Integration
    CAS_ENABLED = True  # Check new members against CAS database
    CAS_AUTO_BAN = True  # Auto-ban users found in CAS database
    CAS_API_URL = "https://api.cas.chat/check"  # CAS API endpoint
    
    # Media/Sticker Spam Detection
    MEDIA_SPAM_DETECTION_ENABLED = True
    BLOCK_MEDIA_FROM_NEW_USERS = True  # Block photos/videos/stickers from new users
    MEDIA_NEW_USER_HOURS = 24  # Hours before new users can send media
    BLOCK_STICKERS_FROM_NEW_USERS = True  # Block stickers from new users
    BLOCK_GIFS_FROM_NEW_USERS = True  # Block GIFs/animations from new users
    MAX_MEDIA_PER_MINUTE = 3  # Max media messages per user per minute (spam detection)
    MEDIA_SPAM_ACTION = "delete_and_warn"  # "delete", "delete_and_warn", "delete_and_mute"
    
    # Forward Message Handling
    BLOCK_FORWARDS = True
    FORWARD_ALLOW_ADMINS = True
    FORWARD_ALLOW_VIP = True
    FORWARD_INSTANT_MUTE = True  # Mute user immediately on forward (not just warn)
    FORWARD_BAN_ON_REPEAT = True  # Ban if user forwards again after mute
    
    # Welcome Message
    SEND_WELCOME_MESSAGE = False  # Don't auto-send welcome (users can use /guidelines)
    WELCOME_MESSAGE = """👋 Welcome to the group!

📋 <b>Rules:</b>
• No spam or scams
• No bad language
• Be respectful
• No advertising without permission

⚠️ Violations will result in warnings, mutes, or bans."""
    
    # Auto-delete join/exit messages
    DELETE_JOIN_EXIT_MESSAGES = True
    
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
    GUIDELINES_MESSAGE = """� <b>Mudrex Telegram Community Guidelines</b>

Welcome to the official Mudrex Telegram community! This is your space to learn, share, and grow as a crypto trader and investor — together.

<i>This group is actively moderated to ensure quality discussions, safety, and clarity for all users.</i>

━━━━━━━━━━━━━━━━━━━━

🎯 <b>What This Community Is For</b>

• Learning about crypto — from charts to concepts
• Getting the most out of the Mudrex app
• Sharing tips, strategies, and experiences with other traders
• Staying updated on Mudrex features and campaigns

━━━━━━━━━━━━━━━━━━━━

🔏 <b>Code of Conduct</b>

<b>1. Respect Everyone</b>
Politeness is non-negotiable. No trolling, abuse, hate speech, or discrimination. No personal attacks. Ever.

<b>2. Zero Tolerance for Link Sharing</b>
No posting external links, referral codes, or promotions — even if they're related to crypto. Repeated violations = ban.

<b>3. Don't Spam</b>
Keep discussions meaningful. No flooding or repetitive messages.

<b>4. Protect Your Privacy</b>
Never share wallet addresses, login screenshots, emails, or account details.
Need help? → <b>help@mudrex.com</b>

━━━━━━━━━━━━━━━━━━━━

📚 <b>Posting Guidelines</b>

✅ <b>Encouraged</b>
• "How do I set a trailing stop-loss on Mudrex Futures?"
• "Any strategy to invest weekly using the SIP mode?"
• "Where can I see my P&L details in the app?"

❌ <b>Not Allowed</b>
• "Check out this new project! [link]"
• "Use my referral code for bonus 💸"

━━━━━━━━━━━━━━━━━━━━

🛠 <b>Help & Feedback</b>

Product issues? → <b>help@mudrex.com</b>

━━━━━━━━━━━━━━━━━━━━

🚨 <b>Admin Discretion</b>

Admins may remove any content or user that goes against the spirit of this community. Bans may be issued without prior warning for serious or repeated violations.

━━━━━━━━━━━━━━━━━━━━

🙌 <b>Final Note</b>

No question is too basic. If you're here to learn, explore, or build — you're welcome.

If you're here to sell, shill, or spam — you're in the wrong place.

<i>Powered by Night Watchman 🌙</i>"""
    
    HELP_MESSAGE = """🌙 <b>Night Watchman Commands</b>

<b>Everyone:</b>
/guidelines - Community rules
/help - This message
/admins - Tag admins for help
/report - Report spam (reply to message)
/rep - Check your reputation
/leaderboard - All-time top users
/leaderboard 7 - Top users (last 7 days)
/leaderboard 30 - Top users (last 30 days)

<b>Admins:</b>
/warn - Warn a user (reply to message)
/mute - Mute a user (reply to message)
/ban - Ban a user (reply to message)
/unwarn - Clear warnings (reply to message)
/enhance - Award +15 points (reply to message)
/stats - Bot statistics
/analytics - Group analytics (DM)

<b>📊 Earning Points:</b>
Daily activity: +5 points
Valid spam report: +10 points
7-day streak bonus: +5 points
30-day streak bonus: +10 points
Admin enhancement (/enhance): +15 points
Warning: -10 points
Muted: -25 points
Unmuted (false positive): +15 points

<i>Powered by Mudrex</i>"""
    
    # Reputation System (Points only - no perks/restrictions)
    # Points are for tracking engagement and can be used for campaigns
    REPUTATION_ENABLED = True
    REP_DAILY_ACTIVE = 5             # Points for daily activity (increased from 1)
    REP_VALID_REPORT = 10            # Points for valid spam report
    REP_WARNING_PENALTY = 10         # Points lost for warning
    REP_MUTE_PENALTY = 25            # Points lost for mute
    REP_UNMUTE_BONUS = 15            # Points for being unmuted (false positive)
    REP_ADMIN_ENHANCEMENT = 15       # Points for admin emoji enhancement on user's message (max once per message)
    REP_7DAY_STREAK_BONUS = 5        # Extra points for 7-day active streak (total: 7x5 + 5 = 40)
    REP_30DAY_STREAK_BONUS = 10      # Extra points for 30-day active streak (total: 30x5 + 10 = 160)
    REP_EXCLUDE_ADMINS = True        # Exclude admins from reputation tracking
    
    # Reputation Levels (display only - NO perks/restrictions)
    REP_LEVEL_MEMBER = 50       # Display level only
    REP_LEVEL_TRUSTED = 200     # Display level only
    REP_LEVEL_VIP = 500         # Display level only
    
    # Forward Detection (applies to ALL users equally)
    BLOCK_FORWARDS = True
    FORWARD_ALLOW_ADMINS = True
    # REMOVED: VIP forward bypass - forwards blocked for everyone except admins
    
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
