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
    MUTE_DURATION_HOURS = 24
    
    # Logging
    LOG_FILE = "logs/night_watchman.log"
    LOG_LEVEL = "INFO"
