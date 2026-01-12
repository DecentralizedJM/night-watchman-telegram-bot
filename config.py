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
        
        # Gemini Bait: Keywords that might be safe but warrant AI inspection
        # These give a low score (0.3) which triggers Gemini scan if enabled
        "check bio", "link in bio", "bio link", "see bio",
        "sniper bot", "mev bot", "front run bot", 
        "win rate", "winning rate", "accuracy", 
        "backtest", "strategies", "automated system",
        "passive income", "steady income",

        # New scam patterns (Dec 2025)
        "trading account is thriving",
        "provided financial assistance",
        "withdrawals are straightforward",
        "from food stamps to $",
        "profit Mrs @",
        "automated trading system based on market conditions",
        "avoids risky strategies like martingale",
        "aims for a daily performance of",
        "ea operates on the m5 timeframe",
        "compatible with all brokers",
        "manages sl/tp",
        "works 24/5 on mt4 and mt5",
        "funded account challenges",
        "send me a dm for more proof",
        
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
        "52casino", "reward received", "successfully received",  # NEW: 52casino specific
        "sign up here:", "dont forget", "start playing",  # NEW: Casino CTAs
        
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
        
        # Recruitment/Job Scam Patterns (new)
        "opening recruitment", "opening a recruitment",
        "recruiting for a project", "recruitment for a project",
        "remote project", "completely remote",
        "actions according to", "tasks according to instructions",
        "earnings from $", "income from $", "earn from $",
        "per day", "per week",  # Only triggers when combined with earnings context
        "putting together a team", "putting together a small team",
        "join a project", "join my team",
        "looking for partners", "looking for people", "looking for several",
        "looking for responsible", "looking for 2-3 people", "looking for two people",
        "full training and support", "we provide training",
        "simple tasks", "clear instructions",
        "daily payments", "everything is transparent",
        "1-2 hours per day", "1.5-2 hours per day", "1–2 hours",
        "send me a private message", "write to me at",
    ]
    
    # INSTANT BAN keywords (no warnings, immediate ban)
    INSTANT_BAN_KEYWORDS = [
        # Adult/Porn
        "xxx", "porn", "p-o-r-n", "x x x", "p o r n",
        "onlyfans", "only fans", "nudes",
        # Casino/Betting (specific, not generic)
        "1win", "1xbet", "xwin", "22bet", "melbet", "mostbet",
        "52casino", "52 casino", ".52casino.cc", "52casino.cc",  # NEW: Specific casino from screenshots
        "casino bonus", "welcome bonus", "free spins",
        "winning streak", "top prize", "grab bonus", "telegram bonus",
        "on your balance", "get your balance", "activate promo",
        "play anywhere", "bet220", "promocasbot",
        "reward received", "your reward has been", "reward has been successfully",  # NEW: Casino reward messages
        "congratulations!", "won $100", "won $200", "$100 instantly",  # NEW: Specific amounts (note: removed space after !)
        "promo code \"lucky", "enter promo code", "dont forget: enter promo",  # NEW: Promo code patterns
        "start playing today", "cash out", "withdraw",  # NEW: Casino CTAs
        # Scam patterns
        "dm me now", "inbox me", "message me now",
        # Recruitment scam instant ban patterns
        "write \"+\"", "leave a \"+\"", "send \"+\"",  # Classic recruitment scam CTA
        "write + in private", "leave + here",
        "earnings from $1", "income: starting at $",  # Specific dollar claims
        "earn a steady extra $", "extra $500", "extra $1,000",
        "$120 per day", "$190 per day", "$250 per day",
        "$1050 per week", "$1,050 per week", "$1000 per week",

        # New scam patterns (Dec 2025)
        "trading account is thriving",
        "provided financial assistance",
        "withdrawals are straightforward",
        "from food stamps to $",
        "profit Mrs @",
        "automated trading system based on market conditions",
        "avoids risky strategies like martingale",
        "aims for a daily performance of",
        "ea operates on the m5 timeframe",
        "compatible with all brokers",
        "manages sl/tp",
        "works 24/5 on mt4 and mt5",
        "funded account challenges",
        "send me a dm for more proof",
    ]
    
    # Whitelisted terms - NEVER trigger spam even if they contain keywords
    # This prevents false positives for legitimate questions
    WHITELISTED_PHRASES = [
        "mudrex promo",
        "promo code in mudrex",
        "promo codes in mudrex", 
        "mudrex referral",
        "how to get promo",
        "where to find promo",
        "any promo code",
        "promo code for mudrex",
    ]
    
    # Money/Dollar emojis - suspicious when used by new users
    # These are often used in scam/promo messages
    MONEY_EMOJIS = ['💰', '💵', '💸', '🤑', '💲', '💳', '🏧', '💎', '🪙', '💴', '💶', '💷']
    
    # New user money emoji detection settings
    MONEY_EMOJI_CHECK_ENABLED = True
    MONEY_EMOJI_NEW_USER_HOURS = 48  # Check users who joined within this time
    MONEY_EMOJI_MIN_REP = 1  # Users with less than this rep are flagged
    MONEY_EMOJI_THRESHOLD = 2  # Number of money emojis to trigger (2+ = suspicious)
    MONEY_EMOJI_ACTION = "delete_and_warn"  # "delete", "delete_and_warn", "delete_and_mute"
    
    # Suspicious URL patterns
    SUSPICIOUS_DOMAINS = [
        "bit.ly", "tinyurl", "t.co", "goo.gl",  # URL shorteners (often abused)
        "telegram.me", "t.me",  # External telegram links
        # Add known scam domains
    ]
    
    # Whitelisted domains (always allowed)
    WHITELISTED_DOMAINS = [
        "mudrex.com",
        "mudrex.go.link",
        "coingecko.com",
        "coinmarketcap.com",
        "tradingview.com",
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
    FORWARD_INSTANT_BAN = True  # INSTANT BAN on forward (not mute) - stops spam immediately
    FORWARD_INSTANT_MUTE = False  # Mute user immediately on forward (legacy, use INSTANT_BAN instead)
    FORWARD_BAN_ON_REPEAT = True  # Ban if user forwards again after mute (if not using instant ban)
    
    # Premium/Custom Emoji Spam Detection
    PREMIUM_EMOJI_SPAM_ENABLED = True
    PREMIUM_EMOJI_THRESHOLD = 3  # 3+ custom/premium emojis = spam (normal users rarely use this many)
    PREMIUM_EMOJI_NEW_USER_BAN = True  # Instant ban new users (<48h) with premium emoji spam
    
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
    
    # ==================== COMMAND ROUTING ====================
    # Redirect crypto/trading commands to specific topic instead of warning users
    
    # Night Watchman bot commands (always allowed everywhere)
    BOT_COMMANDS = [
        '/start', '/help', '/guidelines', '/admins', '/rep', '/leaderboard',
        '/report', '/warn', '/ban', '/mute', '/unwarn', '/enhance', '/cas',
        '/stats', '/analytics'
    ]
    
    # Crypto/trading commands that should be redirected to Market Intelligence topic
    CRYPTO_COMMANDS = [
        # Price commands
        '/btc', '/eth', '/sol', '/xrp', '/bnb', '/ada', '/doge', '/dot',
        '/matic', '/link', '/avax', '/shib', '/ltc', '/atom', '/uni',
        '/btcusd', '/ethusd', '/solusd', '/xrpusd',
        # Trading commands
        '/price', '/chart', '/ta', '/signal', '/signals',
        '/alert', '/alerts', '/market', '/markets', '/trade', '/trading',
    ]
    
    # Comprehensive list of crypto ticker symbols (to prevent false spam detection)
    # Auto-generated from exchange API - covers 450+ tokens available for trading
    CRYPTO_TICKERS = [
        # A-B
        '0g', '1inch', '2z', 'a8', 'aave', 'ach', 'acs', 'ada', 'aero', 'aevo',
        'afc', 'agi', 'agix', 'agld', 'aioz', 'aixbt', 'akt', 'akash', 'alch', 'algo',
        'alt', 'ami', 'anime', 'ankr', 'ao', 'ape', 'apex', 'apt', 'ar', 'arb',
        'arkm', 'art', 'arty', 'aster', 'ath', 'atom', 'audio', 'aurora', 'ava', 'avail',
        'avax', 'avl', 'avnt', 'axl', 'axs', 'b3', 'baby1', 'bal', 'ban', 'bard',
        'bat', 'bb', 'bbsol', 'bch', 'bdxn', 'beam', 'bel', 'bera', 'bico', 'bigtime',
        'blast', 'blur', 'bmt', 'bnb', 'bnt', 'bob', 'boba', 'bomb', 'bome', 'bone',
        'bonk', 'br', 'brett', 'bsv', 'btc', 'btg', 'btt',
        # C-D
        'c98', 'cake', 'camp', 'carv', 'cat', 'cate', 'cati', 'cbk', 'cc', 'celo',
        'celr', 'cfg', 'cfx', 'cgpt', 'chsb', 'chz', 'city', 'ckb', 'cloud', 'cmeth',
        'coinx', 'common', 'comp', 'cook', 'cookie', 'cope', 'coq', 'core', 'corn', 'cpool',
        'cro', 'crv', 'cspr', 'cta', 'ctc', 'ctsi', 'cudis', 'cvx', 'cyber', 'dai',
        'dash', 'dbr', 'dcr', 'deep', 'degen', 'dent', 'dfinity', 'dgb', 'diam', 'dmail',
        'doge', 'dogs', 'dolo', 'dood', 'dot', 'dpx', 'drift', 'dusk', 'dydx', 'dym',
        # E-F
        'eat', 'egld', 'eigen', 'elx', 'ena', 'enj', 'ens', 'enso', 'eos', 'ept',
        'era', 'es', 'ese', 'etc', 'eth', 'ethfi', 'ethw', 'ever', 'fet', 'ff',
        'fhe', 'fida', 'fil', 'fitfi', 'flip', 'flock', 'floki', 'flow', 'flr', 'fluid',
        'flux', 'fort', 'foxy', 'frag', 'frax', 'ftt', 'ftm', 'fuel', 'fxs',
        # G-H
        'gaib', 'gala', 'game', 'glm', 'glmr', 'gmt', 'gmx', 'goat', 'gods', 'gps',
        'grail', 'grass', 'grt', 'gst', 'gt', 'gtai', 'gusd', 'haedal', 'hbar', 'hft',
        'hive', 'hmstr', 'hnt', 'holo', 'home', 'hook', 'hpos', 'ht', 'htx', 'huma',
        'hype', 'hyper',
        # I-J-K
        'icnt', 'icp', 'icx', 'id', 'ilv', 'imx', 'init', 'inj', 'insp', 'inter',
        'io', 'iota', 'iotx', 'ip', 'izi', 'jasmy', 'jet', 'joe', 'jones', 'jst',
        'jto', 'jup', 'juv', 'kaia', 'kas', 'kasta', 'kava', 'kcs', 'kda', 'kilo',
        'kmno', 'knc', 'ksm', 'kub',
        # L-M
        'l3', 'la', 'ladys', 'lava', 'layer', 'lbtc', 'ldo', 'leo', 'linea', 'link',
        'litkey', 'll', 'lmwr', 'lpt', 'lqty', 'lrc', 'ltc', 'luna', 'lunai', 'lunc',
        'lusd', 'magic', 'major', 'mana', 'mango', 'manta', 'masa', 'mask', 'matic', 'mavia',
        'mbox', 'mbx', 'mc', 'mcrt', 'me', 'mee', 'meme', 'memefi', 'merl', 'met',
        'metax', 'metis', 'meth', 'mew', 'milk', 'mim', 'mina', 'mir', 'mkr', 'mmt',
        'mngo', 'mnt', 'moca', 'mode', 'mog', 'mon', 'monpro', 'morpho', 'move', 'movr',
        'mplx', 'mvl', 'mx', 'myro',
        # N-O
        'naka', 'navx', 'near', 'neiro', 'neo', 'neon', 'newt', 'nexo', 'nft', 'nibi',
        'night', 'nkn', 'nmt', 'nom', 'not', 'nrn', 'ns', 'nym', 'oas', 'obol',
        'obt', 'ocean', 'odos', 'ohm', 'okb', 'ol', 'olas', 'om', 'omg', 'ondo',
        'one', 'ont', 'op', 'orca', 'order', 'ordi', 'oxt',
        # P-Q
        'paal', 'parti', 'pell', 'pendle', 'pengu', 'people', 'pepe', 'perp', 'pineye', 'pirate',
        'pixel', 'plume', 'plutus', 'pnut', 'pol', 'poly', 'ponke', 'popcat', 'port', 'port3',
        'portal', 'prcl', 'prime', 'prove', 'psg', 'psyop', 'pstake', 'puff', 'puffer', 'pump',
        'purse', 'pyr', 'pyth', 'pyusd', 'qnt', 'qorpo', 'qtum',
        # R-S
        'raca', 'rad', 'rare', 'rats', 'ray', 'rdnt', 'recall', 'red', 'render', 'req',
        'resolv', 'rlc', 'rlusd', 'rndr', 'roam', 'ron', 'ronin', 'root', 'rose', 'rpl',
        'rsr', 'rss3', 'rune', 'rvn', 'saber', 'safe', 'sahara', 'samo', 'sand', 'saros',
        'sats', 'sbr', 'sc', 'sca', 'scr', 'scroll', 'scrt', 'sd', 'sei', 'send',
        'seraph', 'serum', 'sfp', 'sfund', 'shards', 'shib', 'sidus', 'sign', 'silo', 'sis',
        'skate', 'skl', 'sky', 'slerf', 'slnd', 'slp', 'snx', 'sol', 'solo', 'solv',
        'somi', 'sonic', 'soso', 'spec', 'spell', 'spk', 'spx', 'sqd', 'sqr', 'srm',
        'ssv', 'stable', 'steem', 'step', 'steth', 'storj', 'stream', 'strk', 'stx', 'sui',
        'sun', 'sundog', 'super', 'supra', 'sushi', 'svl', 'sweat', 'swell', 'sxt', 'synd',
        'sys',
        # T-U-V
        'ta', 'tac', 'tai', 'taiko', 'tao', 'tel', 'tfuel', 'thena', 'theta', 'tia',
        'time', 'tnsr', 'token', 'ton', 'toshi', 'towns', 'trc', 'tree', 'trump', 'trvl',
        'trx', 'tulip', 'tuna', 'turbo', 'turbos', 'tusd', 'twt', 'ulti', 'uma', 'uni',
        'usd1', 'usdc', 'usdd', 'usde', 'usdp', 'usdt', 'usdtb', 'usdy', 'ust', 'ustc',
        'uxlink', 'vana', 'vanry', 'velo', 'venom', 'vet', 'vic', 'vinu', 'vra', 'vtho',
        'vvv',
        # W-X-Y-Z
        'w', 'wal', 'waves', 'wax', 'waxp', 'wbtc', 'wct', 'weeth', 'wemix', 'wen',
        'wet', 'weth', 'wif', 'wld', 'wlfi', 'woo', 'wojak', 'wrx', 'xai', 'xan',
        'xaut', 'xava', 'xcad', 'xdc', 'xec', 'xem', 'xion', 'xlm', 'xmr', 'xo',
        'xpl', 'xrp', 'xter', 'xtz', 'xusd', 'x2y2', 'yb', 'yfi', 'ygg', 'zbt',
        'zec', 'zen', 'zent', 'zeta', 'zex', 'zig', 'zil', 'zk', 'zkc', 'zkj',
        'zkl', 'zksync', 'zora', 'zrc', 'zro', 'zrx', 'ztx',
    ]
    
    # Funding rate commands - redirected to Futures Funding Alerts topic
    FUNDING_COMMANDS = [
        '/funding', '/fundingrate', '/fundingrates',
        '/fr',  # Short for funding rate
    ]
    # Also match /funding_btc, /funding_eth, etc. (handled in code)
    
    # Enable crypto command redirection
    CRYPTO_COMMAND_REDIRECT_ENABLED = True
    
    # Topic ID for Market Intelligence (where crypto price commands should go)
    MARKET_INTELLIGENCE_TOPIC_ID = 89270
    MARKET_INTELLIGENCE_TOPIC_NAME = "Mudrex Market Intelligence"
    MARKET_INTELLIGENCE_TOPIC_LINK = "https://t.me/officialmudrex/89270"
    
    # Topic ID for Futures Funding Alerts (where funding commands should go)
    FUNDING_ALERTS_TOPIC_ID = 96073
    FUNDING_ALERTS_TOPIC_NAME = "Futures Funding Alerts"
    FUNDING_ALERTS_TOPIC_LINK = "https://t.me/officialmudrex/96073"
    
    # Message to show when redirecting crypto commands
    CRYPTO_COMMAND_REDIRECT_MESSAGE = """💡 <b>Wrong topic!</b>

This command works in our <a href="{topic_link}">{topic_name}</a> topic.

Please use crypto/trading commands there! 📊"""
    
    # Message to show when redirecting funding commands
    FUNDING_COMMAND_REDIRECT_MESSAGE = """💡 <b>Wrong topic!</b>

Funding rate commands work in our <a href="{topic_link}">{topic_name}</a> topic.

Please use /funding commands there! 📈"""
    
    # Admin User IDs (can access /analytics via DM)
    # Add your Telegram user ID here
    ADMIN_USER_IDS = [
        int(x) for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip()
    ] if os.getenv("ADMIN_USER_IDS") else [395803228]  # Default: @DecentralizedJM
    
    # Analytics Settings
    ANALYTICS_ENABLED = True
    ANALYTICS_RETENTION_DAYS = 90  # Keep data for 90 days
    ANALYTICS_DATA_DIR = os.getenv("ANALYTICS_DATA_DIR", "data")  # Configurable for Railway volumes
    
    # Gemini AI Integration (Free Tier)
    GEMINI_ENABLED = True
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = "gemini-pro"
    GEMINI_RPM_LIMIT = 10  # Conservative limit (Free tier is usually 15-60 RPM depending on region)
    GEMINI_CONFIDENCE_THRESHOLD = 0.8  # Trust Gemini if it's 80% sure
    GEMINI_SCAN_THRESHOLD = 0.3  # Only scan messages that are already slightly suspicious (score > 0.3)
    # Don't waste Gemini quota on obvious safe messages, but use it to catch subtle spam
    
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

    # Safety Tip Message (shown when scammy spam is detected)
    SAFETY_TIP_MESSAGE = """
🛡 <b>Safety Warning:</b>
• Never share OTPs, passwords, or private keys.
• Do not connect your wallet to unknown sites.
• Unbelievable profits = Scams. Always DYOR.
• Be careful interacting with strangers in DMs."""
    
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
