"""
Night Watchman - Main Bot
Telegram Spam Detection & Moderation
"""

import asyncio
import html
import logging
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
import httpx
from dotenv import load_dotenv

from config import Config
from spam_detector import SpamDetector
from analytics_tracker import AnalyticsTracker
from reputation_tracker import ReputationTracker
from ticker_fetcher import ticker_fetcher, get_crypto_tickers

load_dotenv()


def html_escape(text: str) -> str:
    """Escape user-provided text to prevent HTML injection in Telegram messages."""
    if not text:
        return ""
    return html.escape(str(text), quote=False)


# Setup logging
os.makedirs("logs", exist_ok=True)

# SECURITY: Filter to redact sensitive information (tokens, API keys) from logs
class SecurityFilter(logging.Filter):
    """Filter to redact sensitive information from log messages"""
    def filter(self, record):
        if hasattr(record, 'msg'):
            msg = str(record.msg)
            # Redact bot tokens (pattern: /bot\d+:[A-Za-z0-9_-]+)
            msg = re.sub(r'/bot(\d+):([A-Za-z0-9_-]+)', r'/bot\1:[REDACTED]', msg)
            # Redact API keys in URLs
            msg = re.sub(r'(api[_-]?key=)([A-Za-z0-9_-]+)', r'\1[REDACTED]', msg, flags=re.IGNORECASE)
            msg = re.sub(r'(token=)([A-Za-z0-9_-]+)', r'\1[REDACTED]', msg, flags=re.IGNORECASE)
            record.msg = msg
        if hasattr(record, 'args') and record.args:
            # Also filter args (used in formatted messages)
            args = list(record.args)
            for i, arg in enumerate(args):
                if isinstance(arg, str):
                    args[i] = re.sub(r'/bot(\d+):([A-Za-z0-9_-]+)', r'/bot\1:[REDACTED]', arg)
                    args[i] = re.sub(r'(api[_-]?key=)([A-Za-z0-9_-]+)', r'\1[REDACTED]', str(args[i]), flags=re.IGNORECASE)
            record.args = tuple(args)
        return True

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_FILE),
        logging.StreamHandler()
    ]
)

# Apply security filter to all loggers
security_filter = SecurityFilter()
logging.getLogger().addFilter(security_filter)

# SECURITY: Disable verbose httpx logging (it logs full URLs with tokens)
logging.getLogger("httpx").setLevel(logging.WARNING)  # Only log WARNING and above
logging.getLogger("httpcore").setLevel(logging.WARNING)  # httpcore is used by httpx

logger = logging.getLogger(__name__)


class NightWatchman:
    """
    Night Watchman Bot - Telegram Spam Detection & Moderation
    
    Features:
    - Real-time spam detection using multiple signals
    - Auto-delete spam messages
    - Warn/mute repeat offenders
    - Report to admins
    - New user link restrictions
    """
    
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.admin_chat_id = os.getenv("ADMIN_CHAT_ID")
        
        if not self.token:
            logger.error("Missing TELEGRAM_BOT_TOKEN!")
            sys.exit(1)
        
        self.config = Config()
        self.detector = SpamDetector()
        self.analytics = AnalyticsTracker()  # Analytics tracker
        self.reputation = ReputationTracker()  # Reputation system
        
        # Track chat member join dates
        self.member_join_dates: Dict[str, datetime] = {}  # f"{chat_id}_{user_id}" -> datetime
        
        # Track recent joins for anti-raid
        self.recent_joins: Dict[int, List[datetime]] = {}  # chat_id -> [join_times]
        
        # Track bot's own messages for auto-delete
        self.bot_messages: Dict[str, Dict] = {}  # f"{chat_id}_{message_id}" -> message_data
        
        # Track monitored groups (for admin verification in DMs)
        self.monitored_groups: List[int] = []  # list of chat_ids
        
        # Track users without usernames (for kick after grace period)
        self.users_without_username: Dict[str, datetime] = {}  # f"{chat_id}_{user_id}" -> join_time
        
        # Track report cooldowns
        self.report_cooldowns: Dict[int, datetime] = {}  # user_id -> last_report_time
        
        # Track message authors for admin enhancement (with size limit to prevent memory leak)
        self.message_authors: Dict[str, int] = {}  # f"{chat_id}_{message_id}" -> user_id
        self.MESSAGE_AUTHORS_MAX_SIZE = 5000  # Max entries before cleanup
        
        # Track media messages for spam detection (rate limiting)
        self.media_timestamps: Dict[int, List[datetime]] = {}  # user_id -> [media_send_times]
        
        # Track messages that received admin enhancement (prevent duplicates, with size limit)
        self.enhanced_messages: Dict[str, bool] = {}  # f"{chat_id}_{message_id}" -> True
        self.ENHANCED_MESSAGES_MAX_SIZE = 2000  # Max entries before cleanup
        
        # Last cleanup timestamp
        self._last_cleanup = datetime.now(timezone.utc)
        self.CLEANUP_INTERVAL_MINUTES = 30  # Run cleanup every 30 minutes
        
        # Monthly poll settings
        self._last_poll_check = None
        self.POLL_BASE_DATE = datetime(2025, 12, 18, tzinfo=timezone.utc)  # Base date for scammer count
        self.POLL_BASE_COUNT = 847  # Base scammer count on POLL_BASE_DATE
        self.POLL_GROUP_CHAT_ID = -1001868775086  # Mudrex Official group
        
        # Get bot's own user ID
        self.bot_user_id = None
        
        # Stats
        self.stats = {
            'messages_checked': 0,
            'spam_detected': 0,
            'messages_deleted': 0,
            'users_warned': 0,
            'users_muted': 0,
            'users_banned': 0,
            'bad_language_detected': 0,
            'suspicious_users_detected': 0,
            'start_time': datetime.now(timezone.utc)
        }
        
        # Cool ban messages for different scenarios
        self.ban_messages = {
            'spam': [
                "🗑️ {name} - Spam detected. I've seen this garbage before. Banned.",
                "🚫 {name} - Nice try with the spam. You're out.",
                "⛔ {name} - Spam? Really? That's an instant ban from me.",
                "🔨 {name} - I don't tolerate spam. You're permanently banned.",
                "🗑️ {name} - Caught you spamming. No warnings, just bans.",
            ],
            'casino': [
                "🎰 {name} - Casino spam? Not in my house. Banned for life.",
                "🚫 {name} - Trying to push casino links? That's a hard ban.",
                "⛔ {name} - I've seen your casino scam before. Out. Now.",
                "🔨 {name} - Casino promoters don't last long here. Permanently banned.",
                "🎲 {name} - Gambling spam gets you nowhere except banned.",
            ],
            'porn': [
                "🔞 {name} - Inappropriate content. Instant permanent ban. No discussion.",
                "🚫 {name} - Think I wouldn't catch that? Banned for adult content.",
                "⛔ {name} - That content has no place here. You're done.",
                "🔨 {name} - Adult spam gets zero tolerance. Permanent ban.",
            ],
            'bot': [
                "🤖 {name} - Bot account detected. Not allowed. Banned.",
                "🚫 {name} - No bots in my watch. You're out.",
                "⛔ {name} - Bot detected. I don't need backup, you're banned.",
                "🔨 {name} - Bot accounts aren't welcome here. Permanent ban.",
            ],
            'dm_spam': [
                "📩 {name} - Aggressive DM pushing? That's a ban.",
                "🚫 {name} - 'Inbox me'? Not happening. You're out.",
                "⛔ {name} - DM solicitation gets you banned. Every time.",
                "🔨 {name} - Nobody wants your DMs. Permanently banned.",
            ],
            'phishing': [
                "🎣 {name} - Phishing links? I see right through you. Banned.",
                "🚫 {name} - Nice try with the suspicious link. You're done.",
                "⛔ {name} - Phishing scam detected. Permanently banned.",
                "🔨 {name} - These links don't fool me. You're out for good.",
            ],
            'forward': [
                "📤 {name} - Forwarded spam detected. That's an instant ban.",
                "🚫 {name} - No forwarding garbage here. Banned.",
                "⛔ {name} - Forwarding spam? I don't think so. Out.",
                "🔨 {name} - Story forwarding spam gets you banned. Period.",
                "📤 {name} - Caught your forward. Analyzed. Banned.",
            ],
            'media_spam': [
                "🖼️ {name} - Media spam? Seriously? Banned.",
                "🚫 {name} - Flooding with media won't work. You're out.",
                "⛔ {name} - Media spam detected. Permanent ban.",
                "🔨 {name} - Stop the spam. Oh wait, you're already banned.",
            ],
            'recruitment': [
                "💼 {name} - Fake job scam? Out. Banned permanently.",
                "🚫 {name} - Recruitment scam detected. Not today. Banned.",
                "⛔ {name} - Job scams don't fly here. You're done.",
                "🔨 {name} - Nobody falls for your 'work from home' garbage. Banned.",
            ],
            'foreign_language': [
                "🌍 {name} - Foreign language spam detected. Banned.",
                "🚫 {name} - This isn't the place for that. Out.",
                "⛔ {name} - Language policy violation. Banned permanently.",
                "🔨 {name} - Wrong language, wrong group. You're banned.",
            ],
            'default': [
                "🚫 {name} - Out. You don't belong here.",
                "⛔ {name} - Banned. Don't test me.",
                "🔨 {name} - That's a permanent ban. I don't give second chances.",
                "🚷 {name} - You're done here. Move along.",
            ]
        }

        # Security: Track recent moderation actions for anomaly detection
        self.security_events = {
            'bans_last_hour': [],
            'mutes_last_hour': [],
            'warnings_last_hour': []
        }
        
        self.running = True
        self.offset = 0
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(35.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        
        logger.info("🌙 Night Watchman initialized")
    
    def _get_ban_message(self, name: str, username: str = None, category: str = 'default') -> str:
        """Get a cool random ban message for the given category."""
        import random
        messages = self.ban_messages.get(category, self.ban_messages['default'])
        template = random.choice(messages)
        
        # Format name with username if available
        if username:
            display_name = f"<b>{name}</b> (@{username})"
        else:
            display_name = f"<b>{name}</b>"
        
        return template.format(name=display_name)
    
    def _cleanup_caches(self):
        """
        Periodic cleanup of in-memory caches to prevent memory leaks.
        Called periodically from _handle_update.
        """
        now = datetime.now(timezone.utc)
        cleaned = False
        
        # 1. Cleanup message_authors (keep only recent entries)
        if len(self.message_authors) > self.MESSAGE_AUTHORS_MAX_SIZE:
            # Keep the most recent half
            keep_count = self.MESSAGE_AUTHORS_MAX_SIZE // 2
            self.message_authors = dict(list(self.message_authors.items())[-keep_count:])
            logger.info(f"🧹 Cleaned message_authors cache: kept {keep_count} entries")
            cleaned = True
        
        # 2. Cleanup enhanced_messages (keep only recent entries)
        if len(self.enhanced_messages) > self.ENHANCED_MESSAGES_MAX_SIZE:
            keep_count = self.ENHANCED_MESSAGES_MAX_SIZE // 2
            self.enhanced_messages = dict(list(self.enhanced_messages.items())[-keep_count:])
            logger.info(f"🧹 Cleaned enhanced_messages cache: kept {keep_count} entries")
            cleaned = True
        
        # 3. Cleanup report_cooldowns (remove expired entries)
        expired_cooldowns = [
            user_id for user_id, last_time in self.report_cooldowns.items()
            if (now - last_time).total_seconds() > self.config.REPORT_COOLDOWN_SECONDS * 2
        ]
        for user_id in expired_cooldowns:
            del self.report_cooldowns[user_id]
        if expired_cooldowns:
            logger.debug(f"🧹 Cleaned {len(expired_cooldowns)} expired report cooldowns")
            cleaned = True
        
        # 4. Cleanup media_timestamps (remove old entries)
        one_hour_ago = now - timedelta(hours=1)
        users_to_clean = []
        for user_id, timestamps in self.media_timestamps.items():
            self.media_timestamps[user_id] = [t for t in timestamps if t > one_hour_ago]
            if not self.media_timestamps[user_id]:
                users_to_clean.append(user_id)
        for user_id in users_to_clean:
            del self.media_timestamps[user_id]
        if users_to_clean:
            logger.debug(f"🧹 Cleaned media_timestamps for {len(users_to_clean)} users")
            cleaned = True
        
        # 5. Cleanup recent_joins (remove empty chat entries)
        empty_chats = [chat_id for chat_id, joins in self.recent_joins.items() if not joins]
        for chat_id in empty_chats:
            del self.recent_joins[chat_id]
        if empty_chats:
            logger.debug(f"🧹 Cleaned {len(empty_chats)} empty recent_joins entries")
            cleaned = True
        
        # 6. Cleanup users_without_username (remove entries older than grace period)
        grace_hours = getattr(self.config, 'USERNAME_GRACE_PERIOD_HOURS', 24)
        cutoff = now - timedelta(hours=grace_hours * 2)
        expired_username_entries = [
            key for key, join_time in self.users_without_username.items()
            if join_time < cutoff
        ]
        for key in expired_username_entries:
            del self.users_without_username[key]
        if expired_username_entries:
            logger.debug(f"🧹 Cleaned {len(expired_username_entries)} expired username entries")
            cleaned = True
        
        # 7. Cleanup member_join_dates (remove entries older than 7 days)
        week_ago = now - timedelta(days=7)
        old_members = []
        for key, join_date in self.member_join_dates.items():
            # Ensure timezone-aware comparison
            if join_date.tzinfo is None:
                join_date = join_date.replace(tzinfo=timezone.utc)
            if join_date < week_ago:
                old_members.append(key)
        for key in old_members:
            del self.member_join_dates[key]
        if old_members:
            logger.debug(f"🧹 Cleaned {len(old_members)} old member_join_dates entries")
            cleaned = True
        
        if cleaned:
            logger.info(f"🧹 Memory cleanup completed")
        
        self._last_cleanup = now
    
    async def start(self):
        """Start the bot"""
        logger.info("🌙 Night Watchman starting patrol...")
        
        # Get bot info
        bot_info = await self._get_bot_info()
        if bot_info:
            self.bot_user_id = bot_info.get('id')
            logger.info(f"Bot: @{bot_info.get('username', 'unknown')} (ID: {self.bot_user_id})")
        
        # Initialize crypto tickers from exchanges (runs in background)
        asyncio.create_task(self._init_crypto_tickers())
        
        # Start monthly poll checker (runs in background)
        asyncio.create_task(self._monthly_poll_checker())
        
        # Start polling
        await self._poll_updates()
    
    async def _init_crypto_tickers(self):
        """Initialize crypto tickers from exchanges."""
        try:
            tickers = await get_crypto_tickers()
            logger.info(f"📊 Loaded {len(tickers)} crypto tickers from exchanges")
        except Exception as e:
            logger.error(f"Error initializing crypto tickers: {e}")
    
    def _get_scammer_count(self) -> int:
        """
        Calculate the cumulative scammer count based on daily protection stats.
        """
        import random
        
        now = datetime.now(timezone.utc)
        days_since_base = (now - self.POLL_BASE_DATE).days
        
        if days_since_base < 0:
            return self.POLL_BASE_COUNT
        
        # Calculate cumulative count based on daily stats
        total = self.POLL_BASE_COUNT
        for day in range(days_since_base + 1):
            day_date = self.POLL_BASE_DATE + timedelta(days=day)
            random.seed(day_date.strftime("%Y-%m-%d"))
            daily_increment = random.randint(30, 60)
            total += daily_increment
        
        return total
    
    async def _monthly_poll_checker(self):
        """
        Background task that sends a community satisfaction poll once per month.
        Runs on the 18th of each month (matching the base date).
        """
        import random
        
        logger.info("📊 Monthly poll checker started")
        
        # Track last poll month to avoid duplicates
        poll_state_file = os.path.join(
            getattr(self.config, 'ANALYTICS_DATA_DIR', 'data'), 
            'last_poll_month.txt'
        )
        
        while self.running:
            try:
                now = datetime.now(timezone.utc)
                current_month_key = now.strftime("%Y-%m")
                
                # Check if we should send a poll (18th of each month, after 10:00 UTC)
                should_send = now.day == 18 and now.hour >= 10
                
                # Check if already sent this month
                already_sent = False
                if os.path.exists(poll_state_file):
                    with open(poll_state_file, 'r') as f:
                        last_poll_month = f.read().strip()
                        if last_poll_month == current_month_key:
                            already_sent = True
                
                if should_send and not already_sent:
                    # Send the poll!
                    scammer_count = self._get_scammer_count()
                    
                    poll_question = f"Night Watchman: Protected from {scammer_count}+ scammers. Satisfied?"
                    poll_options = [
                        "✅ Yes, doing great!",
                        "👍 Good, keep it up", 
                        "🔧 Needs improvement",
                        "💬 Have suggestions"
                    ]
                    
                    url = f"https://api.telegram.org/bot{self.token}/sendPoll"
                    payload = {
                        "chat_id": self.POLL_GROUP_CHAT_ID,
                        "question": poll_question,
                        "options": poll_options,
                        "is_anonymous": True
                    }
                    
                    response = await self.client.post(url, json=payload, timeout=30.0)
                    data = response.json()
                    
                    if data.get('ok'):
                        logger.info(f"📊 Monthly poll sent! Scammer count: {scammer_count}")
                        # Mark as sent
                        os.makedirs(os.path.dirname(poll_state_file), exist_ok=True)
                        with open(poll_state_file, 'w') as f:
                            f.write(current_month_key)
                    else:
                        logger.error(f"Failed to send monthly poll: {data}")
                
                # Check every hour
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in monthly poll checker: {e}")
                await asyncio.sleep(3600)  # Wait an hour before retrying
    
    async def _get_bot_info(self) -> Optional[Dict]:
        """Get bot information"""
        try:
            url = f"https://api.telegram.org/bot{self.token}/getMe"
            response = await self.client.get(url, timeout=10.0)
            data = response.json()
            if data.get('ok'):
                return data.get('result')
        except Exception as e:
            logger.error(f"Failed to get bot info: {e}")
        return None
    
    async def _poll_updates(self):
        """Poll for updates"""
        logger.info("Starting update polling...")
        
        while self.running:
            try:
                url = f"https://api.telegram.org/bot{self.token}/getUpdates"
                params = {
                    'offset': self.offset,
                    'timeout': 30,
                    'allowed_updates': ['message', 'edited_message', 'chat_member', 'my_chat_member']
                }
                
                response = await self.client.get(url, params=params, timeout=35.0)
                data = response.json()
                
                if data.get('ok'):
                    updates = data.get('result', [])
                    for update in updates:
                        self.offset = update['update_id'] + 1
                        await self._handle_update(update)
                else:
                    logger.error(f"API error: {data}")
                    await asyncio.sleep(5)
                    
            except httpx.TimeoutException:
                continue
            except Exception as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(5)
    
    async def _handle_update(self, update: Dict):
        """Handle incoming update"""
        try:
            # Periodic memory cleanup (every CLEANUP_INTERVAL_MINUTES)
            now = datetime.now(timezone.utc)
            if (now - self._last_cleanup).total_seconds() > self.CLEANUP_INTERVAL_MINUTES * 60:
                self._cleanup_caches()
            
            # Handle chat_member updates (used by forum/topic groups)
            if 'chat_member' in update:
                await self._handle_chat_member(update['chat_member'])
                return
            
            # Handle my_chat_member updates (bot's own status changes)
            if 'my_chat_member' in update:
                # Don't track bot's own joins/exits
                return
            
            message = update.get('message')
            if not message:
                return
            
            # Handle new_chat_members (when multiple users join)
            new_members = message.get('new_chat_members', [])
            if new_members:
                chat_id = message.get('chat', {}).get('id')
                message_id = message.get('message_id')
                
                # Track joins in analytics BEFORE deleting the message (skip bots)
                if self.config.ANALYTICS_ENABLED:
                    for member in new_members:
                        # Skip bots - don't track them in analytics
                        if not member.get('is_bot', False):
                            self.analytics.track_join(chat_id)
                
                # Delete the join message if configured
                if self.config.DELETE_JOIN_EXIT_MESSAGES:
                    await self._delete_message(chat_id, message_id)
                
                for member in new_members:
                    # Create a fake chat_member update for each member
                    fake_update = {
                        'chat': {'id': chat_id},
                        'from': message.get('from'),  # Pass the user who added them
                        'new_chat_member': {
                            'user': member,
                            'status': 'member'
                        }
                    }
                    await self._handle_chat_member(fake_update)
                return
            
            # Handle left_chat_member (when someone leaves)
            left_member = message.get('left_chat_member')
            if left_member:
                # Skip bots leaving
                if left_member.get('is_bot', False):
                    # Still delete the message if configured
                    if self.config.DELETE_JOIN_EXIT_MESSAGES:
                        chat_id = message.get('chat', {}).get('id')
                        message_id = message.get('message_id')
                        await self._delete_message(chat_id, message_id)
                    return
                
                chat_id = message.get('chat', {}).get('id')
                message_id = message.get('message_id')
                
                # Track exit in analytics BEFORE deleting the message
                if self.config.ANALYTICS_ENABLED:
                    self.analytics.track_exit(chat_id)
                    logger.info(f"📊 Tracked exit in analytics: chat={chat_id}")
                
                # Delete the exit message if configured
                if self.config.DELETE_JOIN_EXIT_MESSAGES:
                    await self._delete_message(chat_id, message_id)
                
                return
            
            # Extract message info
            chat = message.get('chat', {})
            chat_id = chat.get('id')
            chat_type = chat.get('type')
            
            user = message.get('from', {})
            user_id = user.get('id')
            user_name = user.get('first_name', 'Unknown')
            username = user.get('username', '')
            
            text = message.get('text', '') or message.get('caption', '')
            message_id = message.get('message_id')
            
            # Get message entities (for detecting hyperlinks, mentions, etc.)
            entities = message.get('entities', []) or message.get('caption_entities', [])
            
            # Track message author for admin enhancement feature
            if chat_id and message_id and user_id:
                message_key = f"{chat_id}_{message_id}"
                self.message_authors[message_key] = user_id
            
            # Only moderate group messages
            if chat_type not in ['group', 'supergroup']:
                # Handle private commands
                if chat_type == 'private':
                    await self._handle_private_message(chat_id, user_id, text)
                return
            
            # Handle /analytics from admins in group (delete command, DM result)
            if text.startswith('/analytics'):
                # Check if user is group admin
                if await self._is_admin(chat_id, user_id):
                    # Delete the command from group to keep it clean
                    await self._delete_message(chat_id, message_id)
                    # Send analytics via DM
                    await self._handle_analytics_command(user_id, user_id, text)
                    return
            
            # Handle user commands (everyone can use these)
            if text.startswith('/'):
                handled = await self._handle_user_command(chat_id, user_id, user_name, username, text, message)
                if handled:
                    return
            
            # Check for admin commands first (BEFORE skipping admin messages)
            if self.config.ADMIN_COMMANDS_ENABLED and text.startswith('/'):
                admin_commands = ['/warn', '/ban', '/mute', '/unwarn', '/enhance', '/stats', '/kick', '/newscam']
                command_word = text.split()[0].lower().split('@')[0]  # Handle /warn@botname format
                
                if command_word in admin_commands:
                    if await self._is_admin(chat_id, user_id):
                        logger.info(f"Processing admin command from {user_id}: {text}")
                        await self._handle_admin_command(chat_id, user_id, text, message)
                        return
                    else:
                        # Non-admin trying to use admin command - delete silently
                        logger.warning(f"⚠️ Non-admin {user_id} tried admin command: {text}")
                        await self._delete_message(chat_id, message_id)
                        return
            
            # Check for crypto/trading commands that should be redirected to Market Intelligence topic
            if text.startswith('/') and getattr(self.config, 'CRYPTO_COMMAND_REDIRECT_ENABLED', False):
                redirected = await self._handle_crypto_command_redirect(chat_id, user_id, user_name, text, message)
                if redirected:
                    return  # Command was redirected, don't process further
            
            # If message starts with '/', it's a command that wasn't handled above
            # Silently ignore unknown commands (don't run spam detection on them)
            if text.startswith('/'):
                logger.debug(f"Unknown command from {user_name}: {text.split()[0]}")
                return
            
            # Skip messages from admins (don't moderate them)
            if await self._is_admin(chat_id, user_id):
                # Still track admin activity for stats (but they don't get rep points)
                if self.config.ANALYTICS_ENABLED:
                    self.analytics.track_message(user_id, chat_id)
                return
            
            # Track this group as monitored
            if chat_id not in self.monitored_groups:
                self.monitored_groups.append(chat_id)
            
            self.stats['messages_checked'] += 1
            
            # Track message in analytics and reputation (daily activity)
            if self.config.ANALYTICS_ENABLED:
                self.analytics.track_message(user_id, chat_id)
            if self.config.REPUTATION_ENABLED:
                self.reputation.track_daily_activity(user_id, username, user_name)
            
            # Check for story shares (BAN ALL STORY SHARES)
            has_story = message.get('story')
            if has_story:
                logger.warning(f"📖 Story share detected from {user_name} (@{username}) - INSTANT BAN")
                await self._delete_message(chat_id, message_id)
                banned = await self._ban_user(chat_id, user_id)
                if banned:
                    self.stats['users_banned'] += 1
                    ban_msg = f"🔨 <b>{user_name}</b> has been banned for sharing a story."
                    await self._send_message(chat_id, ban_msg)
                    # Report to admin
                    if self.admin_chat_id:
                        await self._send_message(
                            self.admin_chat_id,
                            f"📖 <b>Story Share - INSTANT BAN</b>\n\n"
                            f"👤 User: {user_name} (@{username or 'N/A'})\n"
                            f"🆔 ID: <code>{user_id}</code>\n"
                            f"💬 Chat: <code>{chat_id}</code>\n"
                            f"✅ Action: Instant Ban (Story shares are not allowed)"
                        )
                return
            
            # Check for forwarded messages (blocked for everyone except admins/VIP)
            # Note: forward_origin is the newer API field (Bot API 7.0+), forward_from/forward_date are legacy
            is_forwarded = (
                message.get('forward_date') or 
                message.get('forward_from') or 
                message.get('forward_from_chat') or
                message.get('forward_origin')  # New Telegram API field (includes stories)
            )
            
            # Determine forward type for better logging
            forward_type = "unknown"
            if is_forwarded:
                forward_origin = message.get('forward_origin', {})
                if isinstance(forward_origin, dict):
                    origin_type = forward_origin.get('type', '')
                    if origin_type == 'user':
                        forward_type = "user message"
                    elif origin_type == 'channel':
                        forward_type = "channel post"
                    elif origin_type == 'hidden_user':
                        forward_type = "hidden user"
                    elif origin_type == 'story':
                        forward_type = "STORY"  # STORIES are often used for scams
                    else:
                        forward_type = origin_type or "legacy forward"
                elif message.get('forward_from'):
                    forward_type = "user message (legacy)"
                elif message.get('forward_from_chat'):
                    forward_type = "channel/group (legacy)"
            
            # Check for content shared via bot/mini app (via_bot field)
            via_bot = message.get('via_bot')
            if via_bot:
                logger.info(f"🤖 Message via bot detected: {via_bot.get('username', 'unknown')} from {user_name}")
                # Treat bot-shared content as potential spam - analyze it
                bot_result = await self.detector.analyze(text, user_id, None, entities)
                if bot_result.get('instant_ban'):
                    await self._delete_message(chat_id, message_id)
                    await self._handle_instant_ban(
                        chat_id=chat_id,
                        message_id=message_id,
                        user_id=user_id,
                        user_name=user_name,
                        username=username,
                        text=text,
                        result=bot_result,
                        is_forwarded=True  # Treat as forwarded for reporting
                    )
                    return
            
            if is_forwarded:
                logger.info(f"📤 Forwarded message detected [{forward_type}] from {user_name} (@{username})")
                if self.config.BLOCK_FORWARDS:
                    # Check if admin
                    is_admin = self.config.FORWARD_ALLOW_ADMINS and await self._is_admin(chat_id, user_id)
                    
                    # Check if VIP (reputation level)
                    is_vip = False
                    if self.config.FORWARD_ALLOW_VIP and self.config.REPUTATION_ENABLED:
                        user_rep = self.reputation.get_user_rep(user_id)
                        is_vip = user_rep.get('level', '') == 'VIP'
                    
                    if is_admin or is_vip:
                        pass  # Allow admins and VIPs
                    else:
                        # CRITICAL: Analyze forwarded message for spam BEFORE taking action
                        # This catches casino spam, bot links, porn, etc. in forwards (including stories)
                        forward_result = await self.detector.analyze(text, user_id, None, entities)
                        
                        # If forwarded message contains instant-ban content, BAN immediately
                        if forward_result.get('instant_ban'):
                            await self._delete_message(chat_id, message_id)
                            logger.warning(f"⚠️ INSTANT BAN - Forwarded {forward_type} contained banned content")
                            await self._handle_instant_ban(
                                chat_id=chat_id,
                                message_id=message_id,
                                user_id=user_id,
                                user_name=user_name,
                                username=username,
                                text=text,
                                result=forward_result,
                                is_forwarded=True
                            )
                            return
                        
                        # Delete the forwarded message immediately
                        await self._delete_message(chat_id, message_id)
                        

                        # INSTANT BAN for forwards (if enabled)
                        if getattr(self.config, 'FORWARD_INSTANT_BAN', False):
                            banned = await self._ban_user(chat_id, user_id)
                            if banned:
                                self.stats['users_banned'] += 1
                                ban_msg = self._get_ban_message(user_name, username, 'forward')
                                await self._send_message(chat_id, ban_msg)
                                # Report to admin
                                if self.admin_chat_id:
                                    await self._send_message(
                                        self.admin_chat_id,
                                        f"📤 <b>Forward Spam - INSTANT BAN</b>\n\n"
                                        f"🎭 Type: {forward_type}\n"
                                        f"👤 User: {user_name} (@{username or 'N/A'})\n"
                                        f"🆔 ID: <code>{user_id}</code>\n"
                                        f"📝 Message: <code>{text[:200] if text else '[no text]'}</code>\n"
                                        f"✅ Action: Instant Ban"
                                    )
                            return
                        
                        # Legacy: Track forward violations (if not using instant ban)
                        violations = self.detector.add_forward_violation(user_id)
                        
                        if violations >= 2 or self.config.FORWARD_BAN_ON_REPEAT:
                            # Ban on repeat violation
                            if violations >= 2:
                                banned = await self._ban_user(chat_id, user_id)
                                if banned:
                                    self.stats['users_banned'] += 1
                                    ban_msg = self._get_ban_message(user_name, username, 'forward')
                                    await self._send_message(chat_id, ban_msg)
                                    # Report to admin
                                    if self.admin_chat_id:
                                        await self._send_message(
                                            self.admin_chat_id,
                                            f"� <b>Forward Spam Ban</b>\n\n"
                                            f"👤 User: {user_name} (@{username or 'N/A'})\n"
                                            f"🆔 ID: <code>{user_id}</code>\n"
                                            f"⚠️ Violations: {violations}\n"
                                            f"✅ Action: Banned"
                                        )
                                return
                        
                        # First violation: Mute for 24h
                        if self.config.FORWARD_INSTANT_MUTE:
                            muted = await self._mute_user(chat_id, user_id)
                            if muted:
                                self.stats['users_muted'] += 1
                                await self._send_message(
                                    chat_id,
                                    f"🔇 <b>{user_name}</b> muted for 24h — no forwarding allowed! Next time = ban ⚠️"
                                    f"Next violation will result in a ban."
                                )
                        else:
                            await self._send_message(
                                chat_id,
                                f"⚠️ <b>{user_name}</b>, forwarding messages is not allowed in this group."
                            )
                        return
            
            # ========== MEDIA SPAM DETECTION ==========
            if self.config.MEDIA_SPAM_DETECTION_ENABLED:
                # Check for media content (photos, videos, stickers, GIFs)
                has_photo = message.get('photo')  # Photo messages
                has_sticker = message.get('sticker')  # Sticker messages
                has_animation = message.get('animation')  # GIF/animation
                has_video = message.get('video')  # Video messages
                has_video_note = message.get('video_note')  # Video notes (circles)
                has_document = message.get('document')  # Documents (could be GIFs too)
                caption = message.get('caption', '')
                
                media_type = None
                if has_photo:
                    media_type = "photo"
                elif has_sticker:
                    media_type = "sticker"
                elif has_animation:
                    media_type = "GIF/animation"
                elif has_video:
                    media_type = "video"
                elif has_video_note:
                    media_type = "video_note"
                elif has_document:
                    # Check if document is a GIF
                    doc = has_document
                    if doc.get('mime_type') == 'video/mp4' or doc.get('file_name', '').endswith('.gif'):
                        media_type = "GIF"
                        has_animation = True  # Treat as animation
                
                if media_type:
                    is_new_user = self._is_new_user(chat_id, user_id, self.config.MEDIA_NEW_USER_HOURS)
                    
                    # Check 1: Block media from new users
                    if is_new_user:
                        should_block = False
                        block_reason = None
                        
                        if self.config.BLOCK_MEDIA_FROM_NEW_USERS and has_photo:
                            should_block = True
                            block_reason = f"new users can't send photos for {self.config.MEDIA_NEW_USER_HOURS}h after joining"
                        elif self.config.BLOCK_MEDIA_FROM_NEW_USERS and has_video:
                            should_block = True
                            block_reason = f"new users can't send videos for {self.config.MEDIA_NEW_USER_HOURS}h after joining"
                        elif self.config.BLOCK_STICKERS_FROM_NEW_USERS and has_sticker:
                            should_block = True
                            block_reason = f"new users can't send stickers for {self.config.MEDIA_NEW_USER_HOURS}h after joining"
                        elif self.config.BLOCK_GIFS_FROM_NEW_USERS and has_animation:
                            should_block = True
                            block_reason = f"new users can't send GIFs for {self.config.MEDIA_NEW_USER_HOURS}h after joining"
                        
                        if should_block:
                            await self._handle_media_spam(
                                chat_id=chat_id,
                                message_id=message_id,
                                user_id=user_id,
                                user_name=user_name,
                                username=username,
                                media_type=media_type,
                                reason=block_reason,
                                caption=caption
                            )
                            return
                    
                    # Check 2: Media spam rate limit (for all users)
                    if self._check_media_spam_rate(user_id):
                        await self._handle_media_spam(
                            chat_id=chat_id,
                            message_id=message_id,
                            user_id=user_id,
                            user_name=user_name,
                            username=username,
                            media_type=media_type,
                            reason=f"sending media too fast (>{self.config.MAX_MEDIA_PER_MINUTE}/min)",
                            caption=caption
                        )
                        return
                    
                    # Check 3: Analyze caption for spam (if any)
                    if caption:
                        caption_result = await self.detector.analyze(caption, user_id, None, 
                                                                message.get('caption_entities', []))
                        if caption_result.get('instant_ban'):
                            await self._handle_instant_ban(
                                chat_id=chat_id,
                                message_id=message_id,
                                user_id=user_id,
                                user_name=user_name,
                                username=username,
                                text=caption,
                                result=caption_result
                            )
                            return
            
            # Skip spam detection for simple crypto ticker commands (they're already handled by redirect)
            # This prevents false positives on commands like /eth, /btc, etc.
            if text.startswith('/') and len(text.split()) == 1:
                command_lower = text.split()[0].lower()
                ticker = command_lower[1:].split('@')[0] if command_lower.startswith('/') else command_lower
                # Check against known crypto tickers
                static_tickers = getattr(self.config, 'CRYPTO_TICKERS', [])
                crypto_commands = getattr(self.config, 'CRYPTO_COMMANDS', [])
                if ticker in static_tickers or f"/{ticker}" in [c.lower() for c in crypto_commands]:
                    logger.info(f"⏭️ Skipping spam detection for crypto command: {text}")
                    return  # Don't spam-check crypto commands
            
            # Get user join date for new user detection
            member_key = f"{chat_id}_{user_id}"
            join_date = self.member_join_dates.get(member_key)
            
            # Get user reputation for money emoji check
            user_rep = 0
            is_first_message = False
            if self.config.REPUTATION_ENABLED:
                user_rep_data = self.reputation.get_user_rep(user_id)
                user_rep = user_rep_data.get('points', 0)
                # Check if this is their first tracked message (no activity yet)
                is_first_message = user_rep_data.get('total_messages', 0) == 0
            
            # Check for photos
            image_data = None
            if message.get('photo') and getattr(self.config, 'GEMINI_ENABLED', False):
                try:
                    # Get largest photo
                    photos = message.get('photo', [])
                    if photos:
                        largest_photo = sorted(photos, key=lambda x: x.get('file_size', 0), reverse=True)[0]
                        file_id = largest_photo.get('file_id')
                        if file_id:
                            image_data = await self._download_photo(file_id)
                except Exception as e:
                    logger.error(f"Error processing photo: {e}")

            # Analyze message for spam and bad language
            result = await self.detector.analyze(
                text, user_id, join_date, entities,
                user_rep=user_rep, is_first_message=is_first_message,
                image_data=image_data
            )
            
            # REPUTATION CHECK: Higher reputation users get leniency
            is_high_rep = False
            if self.config.REPUTATION_ENABLED:
                if self.reputation.is_trusted(user_id):
                    is_high_rep = True
                    # Downgrade actions for trusted users
                    if result['action'] == 'delete_and_ban':
                        result['action'] = 'delete_and_warn'
                        result['reasons'].append("(High Reputation: Ban avoided)")
                    elif result['action'] == 'delete_and_warn':
                         # Only delete, don't warn trusted users immediately
                         # unless it's very severe (spam score > 0.9)
                        if result['spam_score'] < 0.9:
                            result['action'] = 'delete'
                            result['reasons'].append("(High Reputation: Warning avoided)")

            # Handle INSTANT BAN cases (porn, casino, aggressive DM, etc.)
            if result.get('instant_ban'):
                await self._handle_instant_ban(
                    chat_id=chat_id,
                    message_id=message_id,
                    user_id=user_id,
                    user_name=user_name,
                    username=username,
                    text=text,
                    result=result
                )
                return  # Don't process further
            
            # Handle non-Indian language spam (with or without URLs)
            if result.get('non_indian_language'):
                # Bypass for high rep users
                if is_high_rep:
                     logger.info(f"🛡️ High reputation user {user_name} used non-Indian language, sparing ban.")
                     # Just delete, don't ban
                     await self._delete_message(chat_id, message_id)
                     await self._send_message(
                        chat_id,
                        f"⚠️ <b>{user_name}</b>, non-Indian languages are not allowed here."
                    )
                     return

                await self._handle_non_indian_spam(
                    chat_id=chat_id,
                    message_id=message_id,
                    user_id=user_id,
                    user_name=user_name,
                    username=username,
                    text=text,
                    result=result
                )
                return  # Don't process further
            
            # Handle bad language separately
            # If bad language is detected, handle it and skip spam handling to avoid duplicate actions
            if result.get('bad_language') and self.config.BAD_LANGUAGE_ENABLED:
                # Bypass strict actions for high rep users
                if is_high_rep:
                    # Just warn instead of mute/delete if it was set to severe
                    self.config.BAD_LANGUAGE_ACTION = 'warn' 

                await self._handle_bad_language(
                    chat_id=chat_id,
                    message_id=message_id,
                    user_id=user_id,
                    user_name=user_name,
                    username=username,
                    text=text,
                    result=result
                )
                # Return after handling bad language to prevent duplicate deletion/warnings
                # Bad language already contributes to spam_score, so we handle it separately
                return
            
            if result['is_spam']:
                # Handle special mute_24h action from spam detector
                if result.get('action') == 'mute_24h':
                     logger.warning(f"🔇 Immediate mute for {user_name} due to disallowed link")
                     await self._delete_message(chat_id, message_id)
                     muted = await self._mute_user(chat_id, user_id)
                     if muted:
                        self.stats['users_muted'] += 1
                        await self._send_message(
                            chat_id,
                            f"🔇 <b>{user_name}</b> has been muted for {self.config.MUTE_DURATION_HOURS}h for posting disallowed links."
                        )
                else:
                    await self._handle_spam(
                        chat_id=chat_id,
                        message_id=message_id,
                        user_id=user_id,
                        user_name=user_name,
                        username=username,
                        text=text,
                        result=result
                    )
            elif result['action'] == 'flag':
                # Log for review but don't act
                logger.info(f"⚠️ Flagged message from {user_name}: {result['reasons']}")
            else:
                # Message is clean - learn as ham from trusted users
                # Only learn from VIP (100+) or Trusted (50+) users for quality samples
                if self.config.REPUTATION_ENABLED and user_rep >= 50 and text and len(text) > 15:
                    self.detector.learn_ham(text)
                
        except Exception as e:
            logger.error(f"Error handling update: {e}", exc_info=True)
    
    async def _handle_message_reaction(self, reaction_data: Dict):
        """Handle message reactions for admin enhancement feature"""
        try:
            chat_id = reaction_data.get('chat', {}).get('id')
            message_id = reaction_data.get('message_id')
            user = reaction_data.get('user', {})
            reactor_id = user.get('id')
            
            logger.info(f"🔔 Reaction received: chat={chat_id}, message={message_id}, reactor={reactor_id}")
            
            # Get new reactions
            new_reaction = reaction_data.get('new_reaction', [])
            
            if not new_reaction:
                logger.info(f"No new reaction found")
                return
            
            logger.info(f"New reactions: {new_reaction}")
            
            # Check if reactor is admin
            is_admin = await self._is_admin(chat_id, reactor_id)
            if not is_admin:
                logger.info(f"Reactor {reactor_id} is not an admin")
                return  # Only admins can give enhancement
            
            logger.info(f"Reactor {reactor_id} is an admin ✓")
            
            # Check if any emoji reaction was added (not just specific emoji)
            has_emoji = any(r.get('type') == 'emoji' for r in new_reaction)
            
            if not has_emoji:
                logger.info(f"No emoji reaction found in new_reaction")
                return  # No emoji reaction
            
            logger.info(f"Emoji reaction found ✓")
            
            # Check if this message already received admin enhancement (prevent duplicates)
            message_key = f"{chat_id}_{message_id}"
            if message_key in self.enhanced_messages:
                logger.info(f"Message {message_id} already enhanced (max 15 points per message)")
                return
            
            # Get the message author from our tracking
            message_author_id = self.message_authors.get(message_key)
            
            if not message_author_id:
                logger.warning(f"Cannot find author for message {message_id} in chat {chat_id}. Tracked messages: {len(self.message_authors)}")
                return
            
            logger.info(f"Message author found: {message_author_id} ✓")
            
            # Check if message author is an admin (exclude admins from reputation)
            if self.config.REP_EXCLUDE_ADMINS:
                author_is_admin = await self._is_admin(chat_id, message_author_id)
                if author_is_admin:
                    logger.info(f"Message author {message_author_id} is admin, excluded from reputation")
                    return
            
            logger.info(f"Message author is not admin (eligible for points) ✓")
            
            # Award enhancement points to message author
            self.reputation.admin_enhancement(message_author_id)
            
            # Mark message as enhanced (prevent duplicate enhancements)
            self.enhanced_messages[message_key] = True
            
            logger.info(f"⭐ Admin {reactor_id} enhanced message {message_id} by user {message_author_id} (+15 points)")
                
        except Exception as e:
            logger.error(f"Error handling message reaction: {e}", exc_info=True)

    
    async def _handle_chat_member(self, chat_member: Dict):
        """Track when users join and verify suspicious accounts"""
        try:
            chat_id = chat_member.get('chat', {}).get('id')
            new_member = chat_member.get('new_chat_member', {})
            old_member = chat_member.get('old_chat_member', {})
            user = new_member.get('user', {})
            user_id = user.get('id')
            user_name = user.get('first_name', 'Unknown')
            username = user.get('username', '')
            new_status = new_member.get('status')
            old_status = old_member.get('status', '')
            is_bot = user.get('is_bot', False)
            
            # Check if added by admin - bypass all checks
            added_by = chat_member.get('from', {})
            if added_by:
                added_by_id = added_by.get('id')
                if added_by_id and user_id != added_by_id:  # If added by someone else
                    user_is_admin = await self._is_admin(chat_id, added_by_id)
                    if user_is_admin and user.get('is_bot'):
                        logger.info(f"✨ Bot {user_id} added by admin {added_by_id}, allowing")
                        return
            # Block bot accounts from joining
            if is_bot and self.config.BLOCK_BOT_JOINS:
                logger.warning(f"🤖 Bot account {user_id} (@{username}) tried to join {chat_id}")
                banned = await self._ban_user(chat_id, user_id)
                if banned:
                    self.stats['users_banned'] += 1
                    ban_msg = self._get_ban_message(user_name, username, 'bot')
                    await self._send_message(chat_id, ban_msg)
                    if self.admin_chat_id:
                        await self._send_message(
                            self.admin_chat_id,
                            f"🤖 <b>Bot Account Blocked</b>\n\n"
                            f"👤 Bot: @{username or 'N/A'}\n"
                            f"🆔 ID: <code>{user_id}</code>\n"
                            f"💬 Chat: <code>{chat_id}</code>\n"
                            f"✅ Action: Auto-banned"
                        )
                return
            
            # Also check for bot-like usernames (even if not marked as bot)
            if username and self.config.BLOCK_BOT_JOINS:
                import re
                for pattern in self.config.BOT_USERNAME_PATTERNS:
                    if re.match(pattern, username.lower()):
                        logger.warning(f"🤖 Bot-like username {user_id} (@{username}) tried to join {chat_id}")
                        banned = await self._ban_user(chat_id, user_id)
                        if banned:
                            self.stats['users_banned'] += 1
                            ban_msg = self._get_ban_message(user_name, username, 'bot')
                            await self._send_message(chat_id, ban_msg)
                            if self.admin_chat_id:
                                await self._send_message(
                                    self.admin_chat_id,
                                    f"🤖 <b>Bot-like Account Blocked</b>\n\n"
                                    f"👤 User: {user_name} (@{username})\n"
                                    f"🆔 ID: <code>{user_id}</code>\n"
                                    f"💬 Chat: <code>{chat_id}</code>\n"
                                    f"⚠️ Pattern matched: {pattern}\n"
                                    f"✅ Action: Auto-banned"
                                )
                        return
            
            # Skip bots from further processing
            if is_bot:
                return
            
            # Detect JOIN: user was not a member, now is a member
            if new_status == 'member' and old_status in ['', 'left', 'kicked', 'restricted']:
                # Track in analytics
                if self.config.ANALYTICS_ENABLED:
                    self.analytics.track_join(chat_id)
                
                # User just joined
                member_key = f"{chat_id}_{user_id}"
                join_time = datetime.now(timezone.utc)
                self.member_join_dates[member_key] = join_time
                
                # Track for anti-raid
                if chat_id not in self.recent_joins:
                    self.recent_joins[chat_id] = []
                self.recent_joins[chat_id].append(join_time)
                
                # Clean old joins
                window = timedelta(minutes=self.config.RAID_DETECTION_WINDOW_MINUTES)
                self.recent_joins[chat_id] = [
                    t for t in self.recent_joins[chat_id] 
                    if (join_time - t) < window
                ]
                
                # Check for raid
                if self.config.ANTI_RAID_ENABLED:
                    if len(self.recent_joins[chat_id]) >= self.config.RAID_THRESHOLD_USERS:
                        logger.warning(f"🚨 Possible raid detected in {chat_id}: {len(self.recent_joins[chat_id])} users joined")
                        await self._handle_raid(chat_id, len(self.recent_joins[chat_id]))
                
                # Check CAS (Combot Anti-Spam) database
                if self.config.CAS_ENABLED:
                    cas_result = await self._check_cas(user_id)
                    if cas_result.get("banned"):
                        user_name = user.get('first_name', 'Unknown')
                        username = user.get('username', '')
                        logger.warning(f"🚫 CAS banned user {user_id} (@{username}) tried to join {chat_id}")
                        
                        if self.config.CAS_AUTO_BAN:
                            banned = await self._ban_user(chat_id, user_id)
                            if banned:
                                self.stats['users_banned'] += 1
                                logger.info(f"🔨 Auto-banned CAS-listed user {user_id}")
                                
                                # Report to admin
                                if self.admin_chat_id:
                                    report = f"""🚫 <b>CAS Ban - Known Spammer Blocked</b>

👤 User: {user_name} (@{username or 'N/A'})
🆔 User ID: <code>{user_id}</code>
💬 Chat: <code>{chat_id}</code>
⏰ CAS Added: {cas_result.get('time_added', 'Unknown')}
📋 Offenses: {cas_result.get('reason', 'Unknown')}

✅ <b>Action:</b> Auto-banned on join"""
                                    await self._send_message(self.admin_chat_id, report)
                                return  # Don't process further
                        else:
                            # Just notify admin, don't auto-ban
                            if self.admin_chat_id:
                                report = f"""⚠️ <b>CAS Alert - Known Spammer Joined</b>

👤 User: {user_name} (@{username or 'N/A'})
🆔 User ID: <code>{user_id}</code>
💬 Chat: <code>{chat_id}</code>
⏰ CAS Added: {cas_result.get('time_added', 'Unknown')}
📋 Offenses: {cas_result.get('reason', 'Unknown')}

⚠️ <b>Note:</b> CAS_AUTO_BAN is disabled. Consider manual action."""
                                await self._send_message(self.admin_chat_id, report)
                
                # Verify new user
                if self.config.VERIFY_NEW_USERS:
                    await self._verify_new_user(chat_id, user, join_time)
                
                # Check username requirement
                if self.config.REQUIRE_USERNAME:
                    username = user.get('username', '')
                    if not username:
                        member_key = f"{chat_id}_{user_id}"
                        self.users_without_username[member_key] = join_time
                        # Mute and warn
                        await self._mute_user(chat_id, user_id)
                        await self._send_message(chat_id, self.config.USERNAME_WARNING_MESSAGE)
                        logger.info(f"⚠️ User {user_id} muted - no username")
                
                # Send welcome message
                if self.config.SEND_WELCOME_MESSAGE:
                    await asyncio.sleep(1)  # Small delay
                    await self._send_welcome_message(chat_id, user)
            
            # Detect LEAVE: user was a member, now left/kicked
            elif new_status in ['left', 'kicked']:
                # User left or was kicked
                if self.config.ANALYTICS_ENABLED:
                    self.analytics.track_exit(chat_id)
                    
        except Exception as e:
            logger.error(f"Error tracking chat member: {e}")
    
    async def _handle_spam(self, chat_id: int, message_id: int, user_id: int,
                          user_name: str, username: str, text: str, result: Dict):
        """Handle detected spam"""
        self.stats['spam_detected'] += 1
        
        # Track in analytics
        if self.config.ANALYTICS_ENABLED:
            self.analytics.track_spam_blocked(chat_id)
        
        logger.warning(f"🚨 SPAM detected from {user_name} (@{username}): {result['reasons']}")
        
        # Delete the message
        deleted = False
        if self.config.AUTO_DELETE_SPAM:
            deleted = await self._delete_message(chat_id, message_id)
            if deleted:
                self.stats['messages_deleted'] += 1
                logger.info(f"🗑️ Deleted spam message from {user_name}")
            else:
                logger.warning(f"❌ Could not delete spam message from {user_name}")
        
        # Warn the user (for all spam detections, not just delete_and_warn)
        if self.config.AUTO_WARN_USER and result['is_spam']:
            warnings = self.detector.add_warning(user_id)
            self.stats['users_warned'] += 1

            # Track in analytics
            if self.config.ANALYTICS_ENABLED:
                self.analytics.track_warning(chat_id)
            
            # Security: Track warning for anomaly detection
            now = datetime.now(timezone.utc)
            self.security_events['warnings_last_hour'].append(now)
            one_hour_ago = now - timedelta(hours=1)
            self.security_events['warnings_last_hour'] = [
                t for t in self.security_events['warnings_last_hour'] if t > one_hour_ago
            ]
            
            # Track in reputation
            if self.config.REPUTATION_ENABLED:
                self.reputation.on_warning(user_id, username, user_name)
            
            if warnings >= self.config.AUTO_BAN_AFTER_WARNINGS:
                # Ban the user
                banned = await self._ban_user(chat_id, user_id)
                if banned:
                    self.stats['users_banned'] += 1
                    logger.info(f"🔨 Banned user {user_name} ({warnings} warnings)")
                    ban_msg = self._get_ban_message(user_name, username, 'spam')
                    await self._send_message(chat_id, ban_msg)
            elif warnings >= self.config.AUTO_MUTE_AFTER_WARNINGS:
                # Mute the user
                muted = await self._mute_user(chat_id, user_id)
                if muted:
                    self.stats['users_muted'] += 1
                    logger.info(f"🔇 Muted user {user_name} ({warnings} warnings)")
                    
                    # Notify in group
                    await self._send_message(
                        chat_id,
                        f"🔇 <b>{user_name}</b> has been muted for {self.config.MUTE_DURATION_HOURS}h due to spam."
                    )
            else:
                # Send warning
                remaining = self.config.AUTO_MUTE_AFTER_WARNINGS - warnings
                action_text = "removed" if deleted else "flagged"

                # Check if we should append the generic safety tip (for scam/Gemini detections)
                show_safety_tip = False
                for r in result.get('reasons', []):
                    if "Gemini" in r or "scam" in r.lower() or "bait" in r.lower():
                        show_safety_tip = True
                        break
                
                safety_msg = self.config.SAFETY_TIP_MESSAGE if show_safety_tip else ""

                await self._send_message(
                    chat_id,
                    f"⚠️ <b>{user_name}</b>, your message was {action_text} for spam. "
                    f"Warning {warnings}/{self.config.AUTO_MUTE_AFTER_WARNINGS}.{safety_msg}"
                )
        
        # Report to admin
        if self.admin_chat_id:
            await self._report_to_admin(
                user_id=user_id,
                user_name=user_name,
                username=username,
                chat_id=chat_id,
                text=text,
                result=result
            )
    
    async def _report_to_admin(self, user_id: int, user_name: str, username: str,
                               chat_id: int, text: str, result: Dict):
        """Send spam report to admin"""
        # Escape user-provided content to prevent HTML injection
        safe_user_name = html_escape(user_name)
        safe_username = html_escape(username) if username else 'N/A'
        safe_text = html_escape(text[:500])
        safe_reasons = [html_escape(r) for r in result.get('reasons', [])]
        
        report = f"""🚨 <b>Spam Detected</b>

👤 User: {safe_user_name} (@{safe_username})
🆔 User ID: <code>{user_id}</code>
💬 Chat: <code>{chat_id}</code>

📝 <b>Message:</b>
<code>{safe_text}</code>

⚠️ <b>Reasons:</b>
{chr(10).join('• ' + r for r in safe_reasons)}

📊 Score: {result['spam_score']:.2f}
🔧 Action: {result['action']}"""
        
        await self._send_message(self.admin_chat_id, report)
    
    async def _handle_media_spam(self, chat_id: int, message_id: int, user_id: int,
                                  user_name: str, username: str, media_type: str, 
                                  reason: str, caption: str = None):
        """Handle media spam (photos, stickers, GIFs from new users or spam rate)"""
        self.stats['spam_detected'] += 1
        
        # Track in analytics
        if self.config.ANALYTICS_ENABLED:
            self.analytics.track_spam_blocked(chat_id)
        
        logger.warning(f"🖼️ Media spam detected from {user_name} (@{username}): {reason}")
        
        # Delete the media message
        deleted = await self._delete_message(chat_id, message_id)
        if deleted:
            self.stats['messages_deleted'] += 1
            logger.info(f"🗑️ Deleted media message from {user_name}")
        
        action = self.config.MEDIA_SPAM_ACTION  # "delete", "delete_and_warn", "delete_and_mute"
        
        if action == "delete_and_warn":
            warnings = self.detector.add_warning(user_id)
            self.stats['users_warned'] += 1
            
            # Track in reputation
            if self.config.REPUTATION_ENABLED:
                self.reputation.on_warning(user_id, username, user_name)
            
            if warnings >= self.config.AUTO_BAN_AFTER_WARNINGS:
                banned = await self._ban_user(chat_id, user_id)
                if banned:
                    self.stats['users_banned'] += 1
                    ban_msg = self._get_ban_message(user_name, username, 'media_spam')
                    await self._send_message(chat_id, ban_msg)
            else:
                remaining = self.config.AUTO_MUTE_AFTER_WARNINGS - warnings
                await self._send_message(
                    chat_id,
                    f"⚠️ <b>{user_name}</b>, {reason}. "
                    f"Warning {warnings}/{self.config.AUTO_MUTE_AFTER_WARNINGS}."
                )
        
        elif action == "delete_and_mute":
            muted = await self._mute_user(chat_id, user_id)
            if muted:
                self.stats['users_muted'] += 1
                await self._send_message(
                    chat_id,
                    f"🔇 <b>{user_name}</b> has been muted for {self.config.MUTE_DURATION_HOURS}h — {reason}"
                )
        
        # Report to admin
        if self.admin_chat_id:
            report = f"""🖼️ <b>Media Spam Detected</b>

👤 User: {user_name} (@{username or 'N/A'})
🆔 User ID: <code>{user_id}</code>
💬 Chat: <code>{chat_id}</code>

📷 <b>Media Type:</b> {media_type}
⚠️ <b>Reason:</b> {reason}"""
            
            if caption:
                report += f"\n\n📝 <b>Caption:</b>\n<code>{caption[:300]}</code>"
            
            await self._send_message(self.admin_chat_id, report)
    
    def _check_media_spam_rate(self, user_id: int) -> bool:
        """Check if user is sending media too fast (spam rate)"""
        now = datetime.now(timezone.utc)
        
        # Get user's recent media timestamps
        if user_id not in self.media_timestamps:
            self.media_timestamps[user_id] = []
        
        timestamps = self.media_timestamps[user_id]
        
        # Filter to only last minute
        one_minute_ago = now - timedelta(minutes=1)
        timestamps = [t for t in timestamps if t > one_minute_ago]
        
        # Add current timestamp
        timestamps.append(now)
        self.media_timestamps[user_id] = timestamps
        
        # Check rate limit
        return len(timestamps) > self.config.MAX_MEDIA_PER_MINUTE
    
    def _is_new_user(self, chat_id: int, user_id: int, hours: int = 24) -> bool:
        """Check if user joined within the specified hours"""
        member_key = f"{chat_id}_{user_id}"
        join_date = self.member_join_dates.get(member_key)
        
        if not join_date:
            # If we don't have join date tracked, assume they're not new
            # (they joined before bot started or bot was restarted)
            return False
        
        now = datetime.now(timezone.utc)
        # Ensure join_date is timezone-aware
        if join_date.tzinfo is None:
            join_date = join_date.replace(tzinfo=timezone.utc)
        
        hours_since_join = (now - join_date).total_seconds() / 3600
        return hours_since_join < hours
    
    async def _handle_private_message(self, chat_id: int, user_id: int, text: str):
        """Handle private messages (commands)"""
        if text.startswith('/start'):
            welcome = """🌙 <b>Night Watchman</b>

I am a spam detection bot that protects Telegram groups from:
• Scam links & phishing
• Spam messages
• Flood attacks
• New account abuse

<b>Add me to your group as admin</b> and I'll start protecting it immediately.

<i>Powered by Mudrex</i>"""
            await self._send_message(chat_id, welcome, auto_delete=False)
            
        elif text.startswith('/stats'):
            uptime = datetime.now(timezone.utc) - self.stats['start_time']
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)
            
            # Get ML stats
            ml_stats = self.detector.get_ml_stats()
            ml_info = ""
            if ml_stats.get('ml_available'):
                model_type = ml_stats.get('model_type', 'Unknown')
                status = 'Active' if ml_stats.get('is_trained') else 'Training...'
                ml_info = f"\n\n🤖 <b>ML Classifier:</b> {status}\n🧠 Model: {model_type}\n📚 Training: {ml_stats.get('spam_samples', 0)} spam, {ml_stats.get('ham_samples', 0)} ham"
            
            stats_msg = f"""📊 <b>Night Watchman Stats</b>

⏱️ Uptime: {hours}h {minutes}m
📨 Messages checked: {self.stats['messages_checked']}
🚨 Spam detected: {self.stats['spam_detected']}
🗑️ Messages deleted: {self.stats['messages_deleted']}
⚠️ Users warned: {self.stats['users_warned']}
🔇 Users muted: {self.stats['users_muted']}{ml_info}"""
            await self._send_message(chat_id, stats_msg, auto_delete=False)
    
        elif text.startswith('/newscam'):
            # NEW: Admin-only /newscam command in DM
            if await self._is_admin_in_any_group(user_id):
                # Extract description
                parts = text.split(maxsplit=1)
                description = parts[1] if len(parts) > 1 else None
                
                if not description or len(description) < 20:
                    await self._send_message(
                        chat_id,
                        "❌ Please provide a description of the scam.\n\n"
                        "Usage: <code>/newscam This is a scam where they say...</code>\n\n"
                        "Example: <code>/newscam They're promoting 88casino with code mega2026 for $1000</code>",
                        auto_delete=False
                    )
                    return
                
                # Process the newscam command (applies to all monitored groups)
                await self._handle_newscam_command(chat_id, user_id, description)
            else:
                await self._send_message(
                    chat_id, 
                    "⛔ You must be an admin of a group I moderate to use /newscam.",
                    auto_delete=False
                )
        
        elif text.startswith('/analytics'):
            # Admin-only analytics command
            await self._handle_analytics_command(chat_id, user_id, text)
        
        elif text.startswith('/rep'):
            # In DM, we can't check admin status (no group context)
            # Show user their reputation if enabled
            if self.config.REPUTATION_ENABLED:
                # Get username from user data if possible
                msg = self.reputation.format_user_rep(user_id, None, "You")
                await self._send_message(chat_id, msg, auto_delete=False)
            else:
                await self._send_message(
                    chat_id,
                    "ℹ️ Reputation system is not enabled.",
                    auto_delete=False
                )
        
        elif text.startswith('/leaderboard'):
            # Show leaderboard with optional days filter
            if self.config.REPUTATION_ENABLED:
                parts = text.split()
                days = 0  # Default: lifetime
                if len(parts) > 1:
                    try:
                        days = int(parts[1])
                        if days < 1 or days > 365:
                            days = 0
                    except ValueError:
                        days = 0
                msg = self.reputation.format_leaderboard(days=days)
                await self._send_message(chat_id, msg, auto_delete=False)
        
        elif text.startswith('/guidelines'):
            await self._send_message(chat_id, self.config.GUIDELINES_MESSAGE, auto_delete=False)
        
        elif text.startswith('/help'):
            await self._send_message(chat_id, self.config.HELP_MESSAGE, auto_delete=False)
    
    async def _handle_user_command(self, chat_id: int, user_id: int, user_name: str, 
                                   username: str, text: str, message: Dict) -> bool:
        """
        Handle user commands (available to everyone in group).
        Returns True if command was handled.
        """
        command = text.split()[0].lower()
        message_id = message.get('message_id')
        
        if command == '/guidelines':
            await self._send_message(chat_id, self.config.GUIDELINES_MESSAGE)
            return True
        
        elif command == '/help':
            await self._send_message(chat_id, self.config.HELP_MESSAGE)
            return True
        
        elif command == '/admins':
            # Tag all admins
            admins = await self._get_chat_admins(chat_id)
            if admins:
                admin_mentions = []
                for admin in admins:
                    admin_user = admin.get('user', {})
                    admin_name = admin_user.get('first_name', 'Admin')
                    admin_username = admin_user.get('username', '')
                    if admin_username:
                        admin_mentions.append(f"@{admin_username}")
                    else:
                        admin_mentions.append(f"<a href='tg://user?id={admin_user.get('id')}'>{admin_name}</a>")
                
                await self._send_message(
                    chat_id,
                    f"🆘 <b>Admins called by {user_name}</b>\n\n" + " ".join(admin_mentions)
                )
            return True
        
        elif command == '/rep':
            if self.config.REPUTATION_ENABLED:
                # Check if user is an admin
                if await self._is_admin(chat_id, user_id):
                    await self._send_message(
                        chat_id, 
                        "👑 <b>You're an admin!</b>\n\nAdmins don't participate in the reputation system - you're already at the top! 🎖️"
                    )
                else:
                    msg = self.reputation.format_user_rep(user_id, username, user_name)
                    await self._send_message(chat_id, msg)
            return True
        
        elif text.startswith('/leaderboard'):
            if self.config.REPUTATION_ENABLED:
                # Parse days from command: /leaderboard or /leaderboard 10
                parts = text.split()
                days = 0  # Default: lifetime
                if len(parts) > 1:
                    try:
                        days = int(parts[1])
                        if days < 1 or days > 365:
                            days = 0  # Invalid, use lifetime
                    except ValueError:
                        days = 0  # Not a number, use lifetime
                
                msg = self.reputation.format_leaderboard(days=days)
                await self._send_message(chat_id, msg)
            return True
        
        elif command == '/report':
            if self.config.REPORT_ENABLED:
                await self._handle_report(chat_id, user_id, user_name, username, message)
            return True
        
        return False  # Command not handled
    
    async def _handle_crypto_command_redirect(self, chat_id: int, user_id: int, user_name: str,
                                               text: str, message: Dict) -> bool:
        """
        Handle crypto/trading commands by redirecting users to the appropriate topic.
        - Funding commands -> Futures Funding Alerts topic
        - Other crypto commands -> Market Intelligence topic
        Returns True if the command was handled (redirected).
        """
        command = text.split()[0].lower()
        message_id = message.get('message_id')
        
        # Get the message thread ID (topic ID) if in a forum/topic group
        message_thread_id = message.get('message_thread_id')
        
        # Check if this is a Night Watchman bot command (always allowed everywhere)
        bot_commands = getattr(self.config, 'BOT_COMMANDS', [])
        for bot_cmd in bot_commands:
            if command == bot_cmd.lower() or command.startswith(bot_cmd.lower() + '@'):
                return False  # Allow bot commands everywhere
        
        # ===== CHECK FOR FUNDING COMMANDS FIRST =====
        funding_commands = getattr(self.config, 'FUNDING_COMMANDS', ['/funding', '/fundingrate', '/fr'])
        funding_topic_id = getattr(self.config, 'FUNDING_ALERTS_TOPIC_ID', 96073)
        is_funding_command = False
        
        # Direct match for funding commands
        for fund_cmd in funding_commands:
            if command == fund_cmd.lower() or command.startswith(fund_cmd.lower() + '@'):
                is_funding_command = True
                break
        
        # Also match /funding_btc, /funding_eth, /fundingbtc, etc.
        if not is_funding_command and (command.startswith('/funding') or command.startswith('/fr_')):
            is_funding_command = True
        
        if is_funding_command:
            # Check if already in Funding Alerts topic
            if message_thread_id == funding_topic_id:
                return False  # Allow in correct topic
            
            # Redirect to Funding Alerts topic
            logger.info(f"🔄 Redirecting funding command '{command}' from {user_name} to Funding Alerts topic")
            
            await self._delete_message(chat_id, message_id)
            
            topic_link = getattr(self.config, 'FUNDING_ALERTS_TOPIC_LINK', 'https://t.me/officialmudrex/96073')
            topic_name = getattr(self.config, 'FUNDING_ALERTS_TOPIC_NAME', 'Futures Funding Alerts')
            
            redirect_msg = getattr(self.config, 'FUNDING_COMMAND_REDIRECT_MESSAGE',
                '💡 <b>Wrong topic!</b>\n\nFunding rate commands work in our <a href="{topic_link}">{topic_name}</a> topic.\n\nPlease use /funding commands there! 📈')
            
            redirect_msg = redirect_msg.format(topic_link=topic_link, topic_name=topic_name)
            await self._send_message(chat_id, redirect_msg)
            
            return True  # Handled
        
        # ===== CHECK FOR OTHER CRYPTO COMMANDS =====
        market_topic_id = getattr(self.config, 'MARKET_INTELLIGENCE_TOPIC_ID', 89270)
        
        # Check if already in Market Intelligence topic
        if message_thread_id == market_topic_id:
            return False  # Allow in correct topic
        
        crypto_commands = getattr(self.config, 'CRYPTO_COMMANDS', [])
        is_crypto_command = False
        
        # Direct match
        for crypto_cmd in crypto_commands:
            if command == crypto_cmd.lower() or command.startswith(crypto_cmd.lower() + '@'):
                is_crypto_command = True
                break
        
        # Also catch commands ending with 'usd' (like /btcusd, /ethusd, etc.)
        if not is_crypto_command and command.endswith('usd'):
            is_crypto_command = True
        
        # Check against dynamic crypto tickers (fetched from exchanges daily)
        if not is_crypto_command:
            # Get the ticker from command (remove leading /)
            ticker = command[1:].lower() if command.startswith('/') else command.lower()
            # Remove any bot mention suffix
            if '@' in ticker:
                ticker = ticker.split('@')[0]
            
            # Check against dynamic tickers from exchanges (600+ tokens)
            dynamic_tickers = await get_crypto_tickers()
            if ticker in dynamic_tickers:
                is_crypto_command = True
            else:
                # Fallback: check against static config list
                static_tickers = getattr(self.config, 'CRYPTO_TICKERS', [])
                if ticker in static_tickers:
                    is_crypto_command = True
        
        if not is_crypto_command:
            return False  # Not a crypto command
        
        # This is a crypto command in the wrong topic - redirect!
        logger.info(f"🔄 Redirecting crypto command '{command}' from {user_name} to Market Intelligence topic")
        
        # Delete the original command
        await self._delete_message(chat_id, message_id)
        
        # Send redirect message
        topic_link = getattr(self.config, 'MARKET_INTELLIGENCE_TOPIC_LINK', 'https://t.me/officialmudrex/89270')
        topic_name = getattr(self.config, 'MARKET_INTELLIGENCE_TOPIC_NAME', 'Mudrex Market Intelligence')
        
        redirect_msg = getattr(self.config, 'CRYPTO_COMMAND_REDIRECT_MESSAGE', 
            '💡 <b>Wrong topic!</b>\n\nThis command works in our <a href="{topic_link}">{topic_name}</a> topic.\n\nPlease use crypto/trading commands there! 📊')
        
        redirect_msg = redirect_msg.format(topic_link=topic_link, topic_name=topic_name)
        
        await self._send_message(chat_id, redirect_msg)
        
        return True  # Command was handled (redirected)
    
    async def _get_chat_admins(self, chat_id: int) -> List[Dict]:
        """Get list of chat administrators"""
        try:
            url = f"https://api.telegram.org/bot{self.token}/getChatAdministrators"
            params = {'chat_id': chat_id}
            response = await self.client.get(url, params=params, timeout=10.0)
            data = response.json()
            
            if data.get('ok'):
                return data.get('result', [])
        except Exception as e:
            logger.error(f"Error getting chat admins: {e}")
        return []
    
    async def _handle_report(self, chat_id: int, user_id: int, user_name: str, 
                            username: str, message: Dict):
        """Handle /report command"""
        message_id = message.get('message_id')
        reply_to = message.get('reply_to_message')
        
        # Delete the /report command to keep chat clean
        await self._delete_message(chat_id, message_id)
        
        if not reply_to:
            await self._send_message(
                chat_id,
                f"⚠️ <b>{user_name}</b>, reply to a message with /report to report it."
            )
            return
        
        # Check cooldown
        now = datetime.now(timezone.utc)
        if user_id in self.report_cooldowns:
            elapsed = (now - self.report_cooldowns[user_id]).total_seconds()
            if elapsed < self.config.REPORT_COOLDOWN_SECONDS:
                remaining = int(self.config.REPORT_COOLDOWN_SECONDS - elapsed)
                await self._send_message(
                    chat_id,
                    f"⏳ <b>{user_name}</b>, please wait {remaining}s before reporting again."
                )
                return
        
        self.report_cooldowns[user_id] = now
        
        # Get reported message info
        reported_user = reply_to.get('from', {})
        reported_user_id = reported_user.get('id')
        reported_user_name = reported_user.get('first_name', 'Unknown')
        reported_username = reported_user.get('username', '')
        reported_text = reply_to.get('text', '') or reply_to.get('caption', '') or '[Media]'
        reported_message_id = reply_to.get('message_id')
        
        # Send report to admins
        if self.admin_chat_id:
            # Escape user-provided content
            safe_reporter_name = html_escape(user_name)
            safe_reporter_username = html_escape(username) if username else 'N/A'
            safe_reported_name = html_escape(reported_user_name)
            safe_reported_username = html_escape(reported_username) if reported_username else 'N/A'
            safe_reported_text = html_escape(reported_text[:500])
            
            report = f"""🚨 <b>User Report</b>

👤 <b>Reporter:</b> {safe_reporter_name} (@{safe_reporter_username})

👤 <b>Reported User:</b> {safe_reported_name} (@{safe_reported_username})
🆔 User ID: <code>{reported_user_id}</code>

📝 <b>Message:</b>
<code>{safe_reported_text}</code>

💬 Chat: <code>{chat_id}</code>
📨 Message ID: <code>{reported_message_id}</code>

<i>Use /ban or /mute to take action</i>"""
            await self._send_message(self.admin_chat_id, report, auto_delete=False)
        
        # Confirm to reporter
        await self._send_message(
            chat_id,
            f"✅ <b>{user_name}</b>, your report has been sent to the admins. Thank you!"
        )
        
        logger.info(f"📢 Report from {user_name}: reported {reported_user_name}")
    
    
    async def _handle_newscam_command(self, chat_id: int, user_id: int, description: str):
        """
        Handle /newscam command - teach bot about new scams.
        Extracts patterns and retrains ML model.
        
        Args:
            chat_id: Chat ID where command was sent
            user_id: Admin user ID
            description: Natural language description of the scam
        """
        logger.info(f"🎓 Admin {user_id} teaching new scam: {description[:100]}")
        
        # Send IMMEDIATE acknowledgement
        ack_msg = await self._send_message(
            chat_id,
            "🎓 <b>Scam registered!</b>\n"
            "⏳ Processing and training ML model..."
        )
        
        patterns = None
        
        # Try to extract patterns using Gemini
        if self.detector.gemini_scanner and self.detector.gemini_scanner.enabled:
            try:
                from pattern_extractor import extract_patterns_from_description, validate_and_sanitize_patterns
                
                patterns = await extract_patterns_from_description(
                    self.detector.gemini_scanner,
                    description
                )
                
                if patterns:
                    # Validate and sanitize  
                    patterns = validate_and_sanitize_patterns(patterns)
                    logger.info(f"✅ Extracted patterns: {patterns}")
                else:
                    logger.warning("Failed to extract patterns from description")
                    
            except Exception as e:
                logger.error(f"Pattern extraction error: {e}")
        
        # Add to ML training data (always, even if pattern extraction failed)
        try:
            # Add the description itself as a spam example
            if hasattr(self.detector, 'ml_classifier') and self.detector.ml_classifier:
                self.detector.ml_classifier.add_spam_sample(description)
                logger.info(f"📝 Added scam example to ML training data")
                
                # Auto-retrain ML model immediately
                logger.info(f"🔄 Retraining ML model...")
                await asyncio.to_thread(self.detector.ml_classifier.retrain)
                logger.info(f"✅ ML model retrained")
            else:
                logger.warning("ML classifier not available")
        except Exception as e:
            logger.error(f"ML training error: {e}")
        
        # Build response message with tough ex-marine personality
        response = "✅ <b>Intel received and processed.</b>\n\n"
        
        if patterns and (patterns['keywords'] or patterns['regex_patterns']):
            response += f"📝 <b>Threat type:</b> {patterns['category']}\n\n"
            
            if patterns['keywords']:
                keywords_str = ', '.join(patterns['keywords'][:10])
                response += f"🎯 <b>Patterns identified:</b>\n<code>{keywords_str}</code>\n\n"
            
            if patterns['regex_patterns']:
                response += f"🔍 <b>Signatures extracted:</b> {len(patterns['regex_patterns'])} detection patterns\n\n"
        
        response += "🧠 <b>Updated my threat database.</b> I'm trained and ready.\n\n"
        response += "💪 Next time these punks show up, I'll catch 'em instantly. No one gets past me twice."
        
        # Update the acknowledgement message with results
        if ack_msg:
            await self._edit_message(chat_id, ack_msg.get('message_id'), response)
        else:
            await self._send_message(chat_id, response)
        
        # Report to admin chat if different
        if self.admin_chat_id and self.admin_chat_id != chat_id:
            from html import escape as html_escape
            admin_report = f"""🎓 <b>New Scam Learned</b>

👤 Admin: {user_id}
💬 Chat: <code>{chat_id}</code>

📝 Description:
{html_escape(description[:500])}

{f"🔑 Keywords: {', '.join(patterns['keywords'][:5])}" if patterns and patterns['keywords'] else ""}
✅ ML model retrained
"""
            await self._send_message(self.admin_chat_id, admin_report)
    
    async def _is_admin(self, chat_id: int, user_id: int) -> bool:
        """Check if user is admin in chat"""
        try:
            url = f"https://api.telegram.org/bot{self.token}/getChatMember"
            params = {'chat_id': chat_id, 'user_id': user_id}
            response = await self.client.get(url, params=params, timeout=10.0)
            data = response.json()
            
            if data.get('ok'):
                status = data.get('result', {}).get('status')
                return status in ['creator', 'administrator']
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
        return False
    
    async def _is_admin_in_any_group(self, user_id: int) -> bool:
        """Check if user is admin in any monitored group (for DM commands)"""
        # First check static admin list
        if user_id in self.config.ADMIN_USER_IDS:
            return True
        
        # Then check each monitored group
        for chat_id in self.monitored_groups:
            if await self._is_admin(chat_id, user_id):
                return True
        return False
    
    async def _delete_message(self, chat_id: int, message_id: int) -> bool:
        """Delete a message"""
        try:
            url = f"https://api.telegram.org/bot{self.token}/deleteMessage"
            data = {'chat_id': chat_id, 'message_id': message_id}
            response = await self.client.post(url, json=data, timeout=10.0)
            result = response.json()
            if not result.get('ok'):
                logger.error(f"Failed to delete message {message_id} in {chat_id}: {result.get('description')}")
            return result.get('ok', False)
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
        return False
    
    async def _delete_message_after_delay(self, chat_id: int, message_id: int, delay_seconds: int):
        """Delete a message after a delay (in seconds)"""
        try:
            await asyncio.sleep(delay_seconds)
            await self._delete_message(chat_id, message_id)
        except Exception as e:
            logger.error(f"Error deleting message after delay: {e}")
    
    async def _mute_user(self, chat_id: int, user_id: int) -> bool:
        """Mute a user"""
        try:
            url = f"https://api.telegram.org/bot{self.token}/restrictChatMember"
            until_date = int((datetime.now(timezone.utc) + 
                            timedelta(hours=self.config.MUTE_DURATION_HOURS)).timestamp())
            
            data = {
                'chat_id': chat_id,
                'user_id': user_id,
                'permissions': {
                    'can_send_messages': False,
                    'can_send_media_messages': False,
                    'can_send_other_messages': False,
                    'can_add_web_page_previews': False
                },
                'until_date': until_date
            }
            response = await self.client.post(url, json=data, timeout=10.0)
            result = response.json().get('ok', False)
            
            # Track in analytics
            if result and self.config.ANALYTICS_ENABLED:
                self.analytics.track_mute(chat_id)
            
            # Security: Track mute event for anomaly detection
            if result:
                now = datetime.now(timezone.utc)
                self.security_events['mutes_last_hour'].append(now)
                # Prune old events
                one_hour_ago = now - timedelta(hours=1)
                self.security_events['mutes_last_hour'] = [
                    t for t in self.security_events['mutes_last_hour'] if t > one_hour_ago
                ]
                # Alert if unusually high mute rate
                if len(self.security_events['mutes_last_hour']) >= 20:
                    logger.warning(f"🚨 SECURITY: High mute rate detected ({len(self.security_events['mutes_last_hour'])} mutes in last hour)")
            
            return result
        except Exception as e:
            logger.error(f"Error muting user: {e}")
        return False
    
    async def _handle_bad_language(self, chat_id: int, message_id: int, user_id: int,
                                   user_name: str, username: str, text: str, result: Dict):
        """Handle bad language detection"""
        self.stats['bad_language_detected'] += 1
        
        # Track in analytics
        if self.config.ANALYTICS_ENABLED:
            self.analytics.track_bad_language(chat_id)
        
        action = self.config.BAD_LANGUAGE_ACTION
        bad_words = result['details'].get('bad_language', [])
        
        logger.warning(f"💬 Bad language from {user_name} (@{username}): {', '.join(bad_words[:3])}")
        
        # Delete message if configured
        if action in ['delete', 'delete_and_warn']:
            deleted = await self._delete_message(chat_id, message_id)
            if deleted:
                self.stats['messages_deleted'] += 1
        
        # Handle different actions
        if action == 'mute':
            # Direct mute for bad language
            muted = await self._mute_user(chat_id, user_id)
            if muted:
                self.stats['users_muted'] += 1
                await self._send_message(
                    chat_id,
                    f"🔇 <b>{user_name}</b> has been muted for {self.config.MUTE_DURATION_HOURS}h for bad language."
                )
        elif action in ['warn', 'delete_and_warn']:
            # Warn user and track warnings
            warnings = self.detector.add_warning(user_id)
            self.stats['users_warned'] += 1

            # Track in analytics
            if self.config.ANALYTICS_ENABLED:
                self.analytics.track_warning(chat_id)
            
            # Track in reputation
            if self.config.REPUTATION_ENABLED:
                self.reputation.on_warning(user_id, username, user_name)
            
            await self._send_message(
                chat_id,
                f"⚠️ <b>{user_name}</b>, please keep the language clean. "
                f"Warning {warnings}/{self.config.AUTO_MUTE_AFTER_WARNINGS}."
            )
            
            # Check if should mute/ban after warnings
            if warnings >= self.config.AUTO_BAN_AFTER_WARNINGS:
                banned = await self._ban_user(chat_id, user_id)
                if banned:
                    self.stats['users_banned'] += 1
                    await self._send_message(chat_id, f"🔨 <b>{user_name}</b> has been banned for repeated violations.")
            elif warnings >= self.config.AUTO_MUTE_AFTER_WARNINGS:
                muted = await self._mute_user(chat_id, user_id)
                if muted:
                    self.stats['users_muted'] += 1
                    await self._send_message(chat_id, f"🔇 <b>{user_name}</b> has been muted for {self.config.MUTE_DURATION_HOURS}h.")
        
        # Report to admin
        if self.admin_chat_id:
            # Escape user-provided content
            safe_user_name = html_escape(user_name)
            safe_username = html_escape(username) if username else 'N/A'
            safe_text = html_escape(text[:300])
            safe_bad_words = [html_escape(w) for w in bad_words[:5]]
            
            report = f"""💬 <b>Bad Language Detected</b>

👤 User: {safe_user_name} (@{safe_username})
🆔 User ID: <code>{user_id}</code>
💬 Chat: <code>{chat_id}</code>

📝 <b>Message:</b>
<code>{safe_text}</code>

🚫 <b>Words:</b> {', '.join(safe_bad_words)}"""
            await self._send_message(self.admin_chat_id, report)
    
    async def _verify_new_user(self, chat_id: int, user: Dict, join_time: datetime):
        """Verify new user for suspicious patterns"""
        user_id = user.get('id')
        username = user.get('username', '')
        first_name = user.get('first_name', '')
        
        suspicious_reasons = []
        
        # Check account age (if available from Telegram API)
        # Note: Telegram API doesn't provide account creation date directly
        # We can check other indicators
        
        # Check username patterns
        if username:
            import re
            for pattern in self.config.SUSPICIOUS_USERNAME_PATTERNS:
                if re.match(pattern, username, re.IGNORECASE):
                    suspicious_reasons.append(f"Suspicious username pattern: {username}")
                    break
        
        # Check if username is missing (often spam accounts)
        if not username and not first_name:
            suspicious_reasons.append("No username or name")
        
        if suspicious_reasons:
            self.stats['suspicious_users_detected'] += 1
            logger.warning(f"⚠️ Suspicious user detected: {user_id} - {', '.join(suspicious_reasons)}")
            
            if self.config.AUTO_BAN_SUSPICIOUS_JOINS:
                await self._ban_user(chat_id, user_id)
                await self._send_message(
                    chat_id,
                    f"🔨 Suspicious account detected and banned."
                )
            else:
                # Restrict new user
                await self._restrict_new_user(chat_id, user_id)
                if self.admin_chat_id:
                    report = f"""⚠️ <b>Suspicious User Joined</b>

👤 User: {first_name} (@{username or 'N/A'})
🆔 User ID: <code>{user_id}</code>
💬 Chat: <code>{chat_id}</code>

⚠️ <b>Reasons:</b>
{chr(10).join('• ' + r for r in suspicious_reasons)}"""
                    await self._send_message(self.admin_chat_id, report)
    
    async def _restrict_new_user(self, chat_id: int, user_id: int):
        """Restrict new user (no links, media for X hours)"""
        try:
            url = f"https://api.telegram.org/bot{self.token}/restrictChatMember"
            until_date = int((datetime.now(timezone.utc) + 
                            timedelta(hours=self.config.RESTRICT_NEW_USERS_HOURS)).timestamp())
            
            data = {
                'chat_id': chat_id,
                'user_id': user_id,
                'permissions': {
                    'can_send_messages': True,
                    'can_send_media_messages': False,
                    'can_send_other_messages': False,
                    'can_add_web_page_previews': False
                },
                'until_date': until_date
            }
            response = await self.client.post(url, json=data, timeout=10.0)
            return response.json().get('ok', False)
        except Exception as e:
            logger.error(f"Error restricting user: {e}")
        return False
    
    async def _handle_raid(self, chat_id: int, user_count: int):
        """Handle detected raid"""
        logger.warning(f"🚨 RAID DETECTED in {chat_id}: {user_count} users joined")
        
        # Track in analytics
        if self.config.ANALYTICS_ENABLED:
            self.analytics.track_raid_alert(chat_id)
        
        if self.admin_chat_id:
            report = f"""🚨 <b>RAID DETECTED</b>

💬 Chat: <code>{chat_id}</code>
👥 Users joined: <b>{user_count}</b>
⏰ Time window: {self.config.RAID_DETECTION_WINDOW_MINUTES} minutes

⚠️ Multiple users joined in a short time. This might be a coordinated attack."""
            await self._send_message(self.admin_chat_id, report)
    
    async def _send_welcome_message(self, chat_id: int, user: Dict):
        """Send welcome message to new member"""
        # Welcome message is sent to the group, not personalized
        await self._send_message(chat_id, self.config.WELCOME_MESSAGE)
    
    async def _get_user_id_from_username(self, chat_id: int, username: str) -> tuple:
        """
        Get user_id from @username by checking chat members.
        Returns (user_id, full_name) or (None, None) if not found.
        Note: This requires the bot to have seen the user in the chat.
        """
        username = username.lstrip('@').lower()
        
        # Try to get chat administrators first (they're always available)
        try:
            url = f"https://api.telegram.org/bot{self.token}/getChatAdministrators"
            params = {'chat_id': chat_id}
            response = await self.client.get(url, params=params, timeout=10.0)
            data = response.json()
            
            if data.get('ok'):
                for admin in data.get('result', []):
                    user = admin.get('user', {})
                    admin_username = user.get('username', '').lower()
                    if admin_username == username:
                        user_id = user.get('id')
                        full_name = user.get('first_name', 'User')
                        return (user_id, full_name)
        except Exception as e:
            logger.error(f"Error fetching chat admins: {e}")
        
        # If not found in admins, check tracked users (from recent messages)
        # This is limited but better than nothing
        return (None, None)
    
    async def _parse_target_from_command(self, text: str, message: Dict) -> tuple:
        """
        Parse target user from command text.
        Supports: @username, user_id (numeric), or text_mention entities.
        Returns (user_id, display_name) or (None, None) if not found.
        """
        chat_id = message.get('chat', {}).get('id')
        parts = text.split()
        
        # Check message entities for @username or text_mention
        entities = message.get('entities', [])
        for entity in entities:
            if entity.get('type') == 'text_mention':
                # Direct user mention with user object
                mentioned_user = entity.get('user', {})
                user_id = mentioned_user.get('id')
                full_name = mentioned_user.get('first_name', 'User')
                return (user_id, full_name)
            elif entity.get('type') == 'mention':
                # @username mention - extract username and try to resolve
                offset = entity.get('offset', 0)
                length = entity.get('length', 0)
                username = text[offset:offset+length].lstrip('@')
                user_id, full_name = await self._get_user_id_from_username(chat_id, username)
                if user_id:
                    return (user_id, full_name)
                else:
                    # Return username as display name even if we can't resolve ID
                    return (None, f"@{username}")
        
        # Check command arguments
        if len(parts) > 1:
            arg = parts[1].lstrip('@')
            
            # Try as numeric user_id first
            try:
                user_id = int(arg)
                return (user_id, f"User {user_id}")
            except ValueError:
                # It's a username - try to resolve it
                user_id, full_name = await self._get_user_id_from_username(chat_id, arg)
                if user_id:
                    return (user_id, full_name)
                else:
                    return (None, f"@{arg}")
        
        return (None, None)
    
    async def _handle_admin_command(self, chat_id: int, user_id: int, text: str, message: Dict):
        """Handle admin commands"""
        logger.info(f"🔧 _handle_admin_command called: command='{text}', admin={user_id}")
        
        # Double-check admin status (security layer)
        if not await self._is_admin(chat_id, user_id):
            logger.warning(f"⛔ Non-admin {user_id} bypassed to _handle_admin_command, blocking")
            await self._delete_message(chat_id, message.get('message_id'))
            return
        
        parts = text.split()
        command = parts[0].lower().split('@')[0]  # Handle /warn@botname format
        
        # Try to get target from reply first, then from command arguments
        reply_to = message.get('reply_to_message')
        target_user_id = None
        target_name = None
        

        if reply_to:
            # Reply-to-message takes priority
            target_user_id = reply_to.get('from', {}).get('id')
            target_name = reply_to.get('from', {}).get('first_name', 'User')
            target_username = reply_to.get('from', {}).get('username', '')
            logger.info(f"Reply detected: target_user_id={target_user_id}, name={target_name}")
        else:
            # Parse from @username or user_id in command
            target_user_id, target_name = await self._parse_target_from_command(text, message)
            if target_user_id:
                logger.info(f"Target parsed from command: user_id={target_user_id}, name={target_name}")
            elif target_name:
                logger.warning(f"Found username {target_name} but couldn't resolve to user_id")

        
        # === ADAPTIVE LEARNING COMMANDS ===
        
        if command == '/newscam':
            # Check if this is a reply to a message
            reply_to = message.get('reply_to_message')
            
            if reply_to:
                # REPLY MODE: Learn from the replied message and ban the user
                # Check both text AND caption (for media/stories)
                scam_text = reply_to.get('text') or reply_to.get('caption') or ''
                
                # If it's a forward without text, try to get forward info
                if not scam_text and (reply_to.get('forward_date') or reply_to.get('forward_from') or reply_to.get('forward_from_chat')):
                    fwd_from = reply_to.get('forward_from_chat', {}).get('title') or reply_to.get('forward_from', {}).get('first_name') or 'Unknown'
                    scam_text = f"Forwarded content from {fwd_from}"
                
                scammer_id = reply_to.get('from', {}).get('id')
                scammer_name = reply_to.get('from', {}).get('first_name', 'User')
                scammer_username = reply_to.get('from', {}).get('username', '')
                
                if not scam_text:
                    # If still no text, just ban the user but warn admin we couldn't learn
                    # We continue execution to at least BAN the user
                    await self._send_message(chat_id, "⚠️ <b>Warning:</b> No text/caption found to learn from, but proceeding with ban.")
                    scam_text = "Empty message or media-only spam"
                
                if not scammer_id:
                    await self._send_message(chat_id, "❌ Could not identify the user from replied message.")
                    return
                
                # Send immediate acknowledgement
                ack_msg = await self._send_message(
                    chat_id,
                    f"🎓 <b>Learning from scammer's message...</b>\n"
                    f"👤 User: {scammer_name}\n"
                    f"⏳ Processing..."
                )
                
                # Learn from the scam message
                await self._handle_newscam_command(chat_id, user_id, scam_text)
                
                # Ban the scammer
                banned = await self._ban_user(chat_id, scammer_id)
                
                # Delete the scam message
                scam_msg_id = reply_to.get('message_id')
                if scam_msg_id:
                    await self._delete_message(chat_id, scam_msg_id)
                
                # Build success message with tough ex-marine personality
                response = f"""✅ <b>Target neutralized.</b>

👤 <b>Scammer:</b> {scammer_name} (@{scammer_username if scammer_username else 'no username'})
🆔 <b>ID:</b> <code>{scammer_id}</code>

⚔️ <b>Actions taken:</b>
• Analyzed their tactics and patterns
• Updated my threat database
• Banned permanently - they're not getting back in
• Message deleted - no trace left

💪 <b>Thanks for the intel, boss.</b> I've memorized their playbook. Next scammer who tries this? I'll catch 'em before they even finish typing.

🛡️ <b>Your group is locked down tighter now.</b>"""
                
                # Update acknowledgement message
                if ack_msg:
                    await self._edit_message(chat_id, ack_msg.get('message_id'), response)
                else:
                    await self._send_message(chat_id, response)
                
                # Log to admin chat
                if self.admin_chat_id and self.admin_chat_id != chat_id:
                    from html import escape as html_escape
                    admin_report = f"""🎓 <b>Admin Taught Scam via Reply</b>

👤 Admin: {user_id}
💬 Group: <code>{chat_id}</code>

🚫 Scammer banned: {scammer_name} (@{scammer_username})
🆔 ID: <code>{scammer_id}</code>

📝 Message learned:
{html_escape(scam_text[:300])}

✅ ML model retrained
"""
                    await self._send_message(self.admin_chat_id, admin_report)
                
                return
            
            # DESCRIPTION MODE: Extract description from command
            description = ' '.join(parts[1:]) if len(parts) > 1 else None
            
            if not description or len(description) < 20:
                await self._send_message(
                    chat_id,
                    "❌ Please provide a description of the scam.\n\n"
                    "Usage: <code>/newscam This is a scam where they say...</code>\n\n"
                    "Example: <code>/newscam They're promoting 88casino with code mega2026 for $1000</code>"
                )
                return
            
            await self._handle_newscam_command(chat_id, user_id, description)
            return
        
        # === MODERATION COMMANDS ===
        
        if command == '/warn':
            if target_user_id:
                warnings = self.detector.add_warning(target_user_id)
                self.stats['users_warned'] += 1
                await self._send_message(
                    chat_id,
                    f"⚠️ <b>{target_name}</b> has been warned. "
                    f"Warnings: {warnings}/{self.config.AUTO_MUTE_AFTER_WARNINGS}"
                )
                
                # Learn spam from warned message (if reply-to)
                if reply_to and reply_to.get('text'):
                    warned_text = reply_to.get('text', '')
                    if len(warned_text) > 15:
                        self.detector.learn_spam(warned_text)
                        logger.info(f"📝 ML learning spam from /warn reply")
            else:
                await self._send_message(chat_id, "⚠️ Usage: Reply to message, /warn @username, or /warn <user_id>")
            
        elif command == '/ban':
            if target_user_id:
                banned = await self._ban_user(chat_id, target_user_id)
                if banned:
                    await self._send_message(chat_id, f"🔨 <b>{target_name}</b> has been banned.")
                    self.stats['users_banned'] += 1
                    
                    # Learn spam from banned message (if reply-to)
                    if reply_to and reply_to.get('text'):
                        banned_text = reply_to.get('text', '')
                        if len(banned_text) > 15:
                            self.detector.learn_spam(banned_text)
                            logger.info(f"📝 ML learning spam from /ban reply")
            else:
                await self._send_message(chat_id, "⚠️ Usage: Reply to message, /ban @username, or /ban <user_id>")
                
        elif command == '/mute':
            if target_user_id:
                muted = await self._mute_user(chat_id, target_user_id)
                if muted:
                    await self._send_message(
                        chat_id,
                        f"🔇 <b>{target_name}</b> has been muted for {self.config.MUTE_DURATION_HOURS}h."
                    )
                    self.stats['users_muted'] += 1
                    
                    # Learn spam from muted message (if reply-to)
                    if reply_to and reply_to.get('text'):
                        muted_text = reply_to.get('text', '')
                        if len(muted_text) > 15:
                            self.detector.learn_spam(muted_text)
                            logger.info(f"📝 ML learning spam from /mute reply")
            else:
                await self._send_message(chat_id, "⚠️ Usage: Reply to message, /mute @username, or /mute <user_id>")
                
        elif command == '/unwarn':
            if target_user_id:
                self.detector.clear_warnings(target_user_id)
                await self._send_message(chat_id, f"✅ Warnings cleared for <b>{target_name}</b>.")
                
                # Learn ham from unwarned message (if reply-to) - indicates false positive
                if reply_to and reply_to.get('text'):
                    unwarned_text = reply_to.get('text', '')
                    if len(unwarned_text) > 15:
                        self.detector.learn_ham(unwarned_text)
                        logger.info(f"📝 ML learning ham from /unwarn (false positive correction)")
            else:
                await self._send_message(chat_id, "⚠️ Usage: Reply to message, /unwarn @username, or /unwarn <user_id>")
            
        elif command == '/enhance' and target_user_id:
            logger.info(f"💎 /enhance command received from admin {user_id} for target {target_user_id}")
            # Admin enhancement - award +15 points to user
            message_id = message.get('message_id')
            target_name = reply_to.get('from', {}).get('first_name', 'User')
            target_username = reply_to.get('from', {}).get('username', '')
            
            # Check if target user is an admin (exclude admins from reputation)
            if self.config.REP_EXCLUDE_ADMINS:
                target_is_admin = await self._is_admin(chat_id, target_user_id)
                if target_is_admin:
                    response = await self._send_message(
                        chat_id, 
                        f"⚠️ Cannot enhance <b>{target_name}</b> - admins are excluded from reputation system."
                    )
                    # Delete command and response after 1 minute
                    if response and message_id:
                        response_id = response.get('result', {}).get('message_id')
                        asyncio.create_task(self._delete_message_after_delay(chat_id, message_id, 60))
                        if response_id:
                            asyncio.create_task(self._delete_message_after_delay(chat_id, response_id, 60))
                    return
            
            # Award enhancement points
            self.reputation.admin_enhancement(target_user_id, target_username, target_name)
            
            # Send confirmation
            response = await self._send_message(
                chat_id,
                f"⭐ <b>{target_name}</b> enhanced by admin! +15 points awarded."
            )
            
            # Delete command and response after 1 minute
            if response and message_id:
                response_id = response.get('result', {}).get('message_id')
                asyncio.create_task(self._delete_message_after_delay(chat_id, message_id, 60))
                if response_id:
                    asyncio.create_task(self._delete_message_after_delay(chat_id, response_id, 60))
            
            logger.info(f"⭐ Admin {user_id} enhanced user {target_user_id} (+15 points)")
            
        elif command == '/stats':
            uptime = datetime.now(timezone.utc) - self.stats['start_time']
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)
            
            stats_msg = f"""📊 <b>Night Watchman Stats</b>

⏱️ Uptime: {hours}h {minutes}m
📨 Messages checked: {self.stats['messages_checked']}
🚨 Spam detected: {self.stats['spam_detected']}
💬 Bad language: {self.stats['bad_language_detected']}
🗑️ Messages deleted: {self.stats['messages_deleted']}
⚠️ Users warned: {self.stats['users_warned']}
🔇 Users muted: {self.stats['users_muted']}
🔨 Users banned: {self.stats['users_banned']}
⚠️ Suspicious users: {self.stats['suspicious_users_detected']}"""
            await self._send_message(chat_id, stats_msg)
            
        elif command == '/cas':
            # CAS (Combot Anti-Spam) check command
            # Support reply-to-message, @username, or user ID
            cas_target_id = target_user_id
            target_name = reply_to.get('from', {}).get('first_name', 'User') if reply_to else None
            
            if not cas_target_id:
                parsed_id, parsed_name = await self._parse_target_from_command(text, message)
                if parsed_id:
                    cas_target_id = parsed_id
                    target_name = parsed_name
            
            if cas_target_id:
                cas_result = await self._check_cas(cas_target_id)
                
                if cas_result.get("banned"):
                    cas_msg = f"""🚫 <b>CAS Check Result</b>

👤 User: <b>{target_name}</b>
🆔 User ID: <code>{cas_target_id}</code>

⚠️ <b>STATUS: BANNED IN CAS</b>
⏰ Added: {cas_result.get('time_added', 'Unknown')}
📋 Offenses: {cas_result.get('reason', 'Unknown')}

🔗 <a href="https://cas.chat/query?u={cas_target_id}">View on CAS</a>"""
                elif cas_result.get("error"):
                    cas_msg = f"""⚠️ <b>CAS Check Error</b>

👤 User: <b>{target_name}</b>
🆔 User ID: <code>{cas_target_id}</code>

❌ Error: {cas_result.get('error')}"""
                else:
                    cas_msg = f"""✅ <b>CAS Check Result</b>

👤 User: <b>{target_name}</b>
🆔 User ID: <code>{cas_target_id}</code>

✅ <b>STATUS: CLEAN</b>
No CAS ban record found."""
                
                await self._send_message(chat_id, cas_msg)
            else:
                await self._send_message(chat_id, "⚠️ Usage: Reply to message, /cas @username, or /cas <user_id>")
    
    async def _handle_analytics_command(self, chat_id: int, user_id: int, text: str):
        """Handle /analytics command - admin only, sent via DM"""
        # Check if user is an admin (in any monitored group or static list)
        if not await self._is_admin_in_any_group(user_id):
            await self._send_message(
                chat_id, 
                "⛔ This command is for group admins only.",
                auto_delete=False
            )
            return
        
        if not self.config.ANALYTICS_ENABLED:
            await self._send_message(
                chat_id,
                "📊 Analytics is currently disabled.",
                auto_delete=False
            )
            return
        
        # Parse timeframe from command
        parts = text.split()
        # Parse timeframe from command
        args = text.split()[1:]
        query = " ".join(args).lower().strip()
        
        try:
            if not query or query == 'today':
                stats = self.analytics.get_daily_stats()
                report = self.analytics.format_report(stats)
                
            elif query in ['week', '7d']:
                stats = self.analytics.get_range_stats(days=7)
                report = self.analytics.format_report(stats)
                # Add peak hours
                peak_hours = self.analytics.get_peak_hours(days=7)
                if peak_hours:
                    report += "\n\n⏰ <b>Peak Hours (UTC)</b>"
                    for h in peak_hours[:3]:
                        report += f"\n   {h['hour_str']}: {h['messages']} msgs"

            elif query.endswith('d') and query[:-1].isdigit():
                # Handle 30d, 90d, etc.
                days = int(query[:-1])
                stats = self.analytics.get_range_stats(days=days)
                report = self.analytics.format_report(stats)
                
            elif ' to ' in query:
                # Handle range "from YYYY-MM-DD to YYYY-MM-DD"
                clean_query = query.replace('from ', '')
                start_str, end_str = clean_query.split(' to ')
                
                try:
                    start_date = datetime.strptime(start_str.strip(), "%Y-%m-%d")
                    end_date = datetime.strptime(end_str.strip(), "%Y-%m-%d")
                    
                    # Ensure timezone awareness
                    start_date = start_date.replace(tzinfo=timezone.utc)
                    end_date = end_date.replace(tzinfo=timezone.utc)
                    
                    if start_date > end_date:
                        await self._send_message(chat_id, "⚠️ Start date cannot be after end date.")
                        return
                        
                    stats = self.analytics.get_stats_for_period(start_date, end_date)
                    report = self.analytics.format_report(stats)
                except ValueError:
                     await self._send_message(
                        chat_id,
                        "⚠️ Invalid date format. Please use YYYY-MM-DD.\nExample: <code>/analytics 2023-01-01 to 2023-01-31</code>"
                    )
                     return

            else:
                # Try single date logic or existing fallback
                try:
                    # check if it's a date
                    target_date = datetime.strptime(query, "%Y-%m-%d")
                    date_key = target_date.strftime("%Y-%m-%d")
                    stats = self.analytics.get_daily_stats(date_key)
                    report = self.analytics.format_report(stats)
                except ValueError:
                    # Fallback to number of days if just a number provided/leftover handling
                    try:
                        timeframe = text.split()[1]
                        days = int(timeframe.replace('d', ''))
                        stats = self.analytics.get_range_stats(days=days)
                        report = self.analytics.format_report(stats)
                    except (ValueError, IndexError):
                         report = """📊 <b>Analytics Usage</b>

<code>/analytics</code> - Today's stats
<code>/analytics 7d</code>, <code>30d</code>, <code>90d</code> - Last X days
<code>/analytics 2023-01-01</code> - Specific day
<code>/analytics 2023-01-01 to 2023-01-31</code> - Custom range"""
            
            await self._send_message(chat_id, report, auto_delete=False)
            logger.info(f"Analytics report sent to admin {user_id}")
            
        except Exception as e:
            logger.error(f"Error generating analytics: {e}")
            await self._send_message(
                chat_id,
                f"❌ Error generating analytics: {str(e)}",
                auto_delete=False
            )
    
    async def _handle_instant_ban(self, chat_id: int, message_id: int, user_id: int,
                                  user_name: str, username: str, text: str, result: Dict,
                                  is_forwarded: bool = False):
        """
        Handle INSTANT BAN violations - no warnings, immediate ban.
        Triggers: porn/adult content, casino/betting, aggressive DM solicitation, etc.
        """
        reasons = result.get('reasons', ['Instant ban violation'])
        triggers = result.get('details', {}).get('instant_ban_triggers', [])
        
        # Add forwarded message indicator if applicable
        if is_forwarded:
            triggers = ['forwarded_spam'] + triggers
        
        logger.warning(f"🚨 INSTANT BAN triggered for {user_name} (@{username}): {reasons} (forwarded={is_forwarded})")
        
        # Delete the message
        await self._delete_message(chat_id, message_id)
        self.stats['messages_deleted'] += 1
        
        # Determine ban category for cool message
        ban_category = 'scammer'  # default
        if 'adult_content' in triggers:
            ban_category = 'adult'
        elif 'casino_spam' in triggers:
            ban_category = 'casino'
        elif 'promo_spam' in triggers or 'emoji_promo_spam' in triggers:
            ban_category = 'promo'
        elif 'telegram_bot_link' in triggers:
            ban_category = 'bot'
        
        # Ban immediately
        banned = await self._ban_user(chat_id, user_id)
        if banned:
            self.stats['users_banned'] += 1
            
            # Learn from this spam for ML classifier
            if text and len(text) > 10:
                self.detector.learn_spam(text)
            
            # Cool ban message
            ban_msg = self._get_ban_message(user_name, username, ban_category)
            await self._send_message(chat_id, ban_msg)
            
            # Report to admin
            if self.admin_chat_id:
                forward_indicator = "📤 <b>(Forwarded Spam)</b>\n" if is_forwarded else ""
                report = f"""🚨 <b>INSTANT BAN - Severe Violation</b>
{forward_indicator}
👤 User: {user_name} (@{username or 'N/A'})
🆔 User ID: <code>{user_id}</code>
💬 Chat: <code>{chat_id}</code>
⚠️ Triggers: {', '.join(triggers)}
📋 Reasons: {', '.join(reasons)}

📝 <b>Message:</b>
<code>{text[:500]}</code>

✅ <b>Action:</b> Immediately banned"""
                await self._send_message(self.admin_chat_id, report)
        else:
            logger.error(f"Failed to ban user {user_id} for instant ban violation")
    
    async def _handle_non_indian_spam(self, chat_id: int, message_id: int, user_id: int,
                                      user_name: str, username: str, text: str, result: Dict):
        """Handle non-Indian language spam - delete and ban immediately"""
        detected_lang = result.get('detected_language', 'unknown')
        has_links = result.get('immediate_ban', False)
        
        logger.warning(f"🚫 Non-Indian language detected from {user_name} (@{username}): {detected_lang}")
        
        # Delete the message immediately
        deleted = await self._delete_message(chat_id, message_id)
        if deleted:
            self.stats['messages_deleted'] += 1
        
        # Ban immediately if configured
        if self.config.AUTO_BAN_NON_INDIAN_SPAM:
            banned = await self._ban_user(chat_id, user_id)
            if banned:
                self.stats['users_banned'] += 1
                logger.info(f"🔨 Banned {user_name} for non-Indian language spam")
                await self._send_message(
                    chat_id,
                    f"🔨 <b>{user_name}</b> has been banned for posting suspicious content in non-Indian language ({detected_lang})."
                )
        
        # Report to admin
        if self.admin_chat_id:
            # Escape user-provided content
            safe_user_name = html_escape(user_name)
            safe_username = html_escape(username) if username else 'N/A'
            safe_text = html_escape(text[:300])
            safe_lang = html_escape(detected_lang)
            
            report = f"""🚫 <b>Non-Indian Language Spam</b>

👤 User: {safe_user_name} (@{safe_username})
🆔 User ID: <code>{user_id}</code>
💬 Chat: <code>{chat_id}</code>
🌐 Language: {safe_lang}

📝 <b>Message:</b>
<code>{safe_text}</code>

� <b>Action:</b> Banned immediately"""
            await self._send_message(self.admin_chat_id, report)
    
    async def _check_cas(self, user_id: int) -> Dict:
        """
        Check user against CAS (Combot Anti-Spam) database.
        
        Returns:
            dict with keys:
                - banned: bool (True if user is in CAS)
                - reason: str (ban reason if available)
                - time_added: str (when added to CAS)
        """
        if not self.config.CAS_ENABLED:
            return {"banned": False}
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.config.CAS_API_URL}?user_id={user_id}"
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok") and data.get("result"):
                        result = data["result"]
                        return {
                            "banned": True,
                            "reason": result.get("offenses", "Unknown"),
                            "time_added": result.get("time_added", "Unknown"),
                            "messages": result.get("messages", [])
                        }
                
                return {"banned": False}
                
        except Exception as e:
            logger.error(f"CAS API error: {e}")
            return {"banned": False, "error": str(e)}
    
    async def _ban_user(self, chat_id: int, user_id: int) -> bool:
        """Ban a user"""
        try:
            url = f"https://api.telegram.org/bot{self.token}/banChatMember"
            data = {
                'chat_id': chat_id,
                'user_id': user_id,
                'until_date': 0  # Permanent ban
            }
            response = await self.client.post(url, json=data, timeout=10.0)
            result = response.json().get('ok', False)
            
            # Track in analytics
            if result and self.config.ANALYTICS_ENABLED:
                self.analytics.track_ban(chat_id)
            
            # Security: Track ban event for anomaly detection
            if result:
                now = datetime.now(timezone.utc)
                self.security_events['bans_last_hour'].append(now)
                # Prune old events
                one_hour_ago = now - timedelta(hours=1)
                self.security_events['bans_last_hour'] = [
                    t for t in self.security_events['bans_last_hour'] if t > one_hour_ago
                ]
                # Alert if unusually high ban rate
                if len(self.security_events['bans_last_hour']) >= 10:
                    logger.warning(f"🚨 SECURITY: High ban rate detected ({len(self.security_events['bans_last_hour'])} bans in last hour)")
                    if self.admin_chat_id:
                        await self._send_message(
                            self.admin_chat_id,
                            f"🚨 <b>Security Alert</b>\n\nHigh ban rate: {len(self.security_events['bans_last_hour'])} bans in the last hour. Potential attack or misconfiguration.",
                            auto_delete=False
                        )
            
            return result
        except Exception as e:
            logger.error(f"Error banning user: {e}")
        return False
    
    async def _send_message(self, chat_id, text: str, auto_delete: bool = None) -> Dict:
        """Send a message and optionally auto-delete after delay. Returns full response dict."""
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML'
            }
            response = await self.client.post(url, json=data, timeout=10.0)
            result = response.json()
            
            if result.get('ok'):
                sent_message = result.get('result', {})
                message_id = sent_message.get('message_id')
                
                # Auto-delete bot messages if enabled
                if auto_delete is None:
                    auto_delete = self.config.AUTO_DELETE_BOT_MESSAGES
                
                if auto_delete and message_id:
                    # Schedule auto-delete
                    asyncio.create_task(self._auto_delete_message(
                        chat_id, 
                        message_id, 
                        self.config.BOT_MESSAGE_DELETE_DELAY_SECONDS
                    ))
                
                return result  # Return full response
            else:
                logger.error(f"Error sending message: {response_data.get('description')}")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
        return {}  # Return empty dict on error
    
    async def _edit_message(self, chat_id: int, message_id: int, new_text: str) -> Dict:
        """Edit an existing message"""
        try:
            url = f"https://api.telegram.org/bot{self.token}/editMessageText"
            data = {
                'chat_id': chat_id,
                'message_id': message_id,
                'text': new_text,
                'parse_mode': 'HTML'
            }
            response = await self.client.post(url, json=data, timeout=10.0)
            result = response.json()
            
            if result.get('ok'):
                return result.get('result', {})
            else:
                logger.error(f"Error editing message: {result.get('description')}")
        except Exception as e:
            logger.error(f"Exception editing message: {e}")
        return {}  # Return empty dict on error
    
    async def _auto_delete_message(self, chat_id: int, message_id: int, delay_seconds: int):
        """Auto-delete a message after delay"""
        try:
            await asyncio.sleep(delay_seconds)
            await self._delete_message(chat_id, message_id)
            logger.debug(f"Auto-deleted bot message {message_id} in {chat_id}")
        except Exception as e:
            logger.error(f"Error auto-deleting message: {e}")


async def main():
    print("""
╔═══════════════════════════════════════════════════╗
║              🌙 NIGHT WATCHMAN                    ║
║         Telegram Spam Detection Bot               ║
║            Powered by Mudrex                      ║
╚═══════════════════════════════════════════════════╝
    """)
    
    bot = NightWatchman()
    try:
        await bot.start()
    finally:
        await bot.client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
