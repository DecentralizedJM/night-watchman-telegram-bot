"""
Night Watchman - Main Bot
Telegram Spam Detection & Moderation
"""

import asyncio
import html
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
import httpx
from dotenv import load_dotenv

from config import Config
from spam_detector import SpamDetector
from analytics_tracker import AnalyticsTracker
from reputation_tracker import ReputationTracker

load_dotenv()


def html_escape(text: str) -> str:
    """Escape user-provided text to prevent HTML injection in Telegram messages."""
    if not text:
        return ""
    return html.escape(str(text), quote=False)


# Setup logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_FILE),
        logging.StreamHandler()
    ]
)
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
    
    async def start(self):
        """Start the bot"""
        logger.info("🌙 Night Watchman starting patrol...")
        
        # Get bot info
        bot_info = await self._get_bot_info()
        if bot_info:
            self.bot_user_id = bot_info.get('id')
            logger.info(f"Bot: @{bot_info.get('username', 'unknown')} (ID: {self.bot_user_id})")
        
        # Start polling
        await self._poll_updates()
    
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
                    'allowed_updates': ['message', 'chat_member']
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
            # Handle new chat members (track join date)
            if 'chat_member' in update:
                await self._handle_chat_member(update['chat_member'])
                return
            
            message = update.get('message')
            if not message:
                return
            
            # Handle new_chat_members (when multiple users join)
            new_members = message.get('new_chat_members', [])
            if new_members:
                chat_id = message.get('chat', {}).get('id')
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
            
            # Skip messages from admins (don't moderate them)
            if await self._is_admin(chat_id, user_id):
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
            
            # Check for forwarded messages
            if message.get('forward_date') or message.get('forward_from') or message.get('forward_from_chat'):
                if self.config.BLOCK_FORWARDS:
                    # Admins can always forward
                    if self.config.FORWARD_ALLOW_ADMINS and await self._is_admin(chat_id, user_id):
                        pass  # Allow
                    # VIPs can forward
                    elif self.reputation.can_forward(user_id):
                        pass  # Allow
                    else:
                        # Delete and warn
                        await self._delete_message(chat_id, message_id)
                        
                        warning_msg = f"⚠️ <b>{user_name}</b>, forwarding messages is not allowed. Build reputation to unlock this feature."
                        if self.config.REPUTATION_ENABLED:
                             # Lower warning penalty for forwarding
                             current_warnings = self.detector.get_warnings(user_id)
                             if current_warnings < 1: # Give one free pass
                                 warning_msg += "\n(First warning free)"
                             else:
                                 self.detector.add_warning(user_id)

                        await self._send_message(
                            chat_id,
                            warning_msg
                        )
                        return
            
            # Get user join date for new user detection
            member_key = f"{chat_id}_{user_id}"
            join_date = self.member_join_dates.get(member_key)
            
            # Check for admin commands first
            if self.config.ADMIN_COMMANDS_ENABLED and text.startswith('/'):
                if await self._is_admin(chat_id, user_id):
                    await self._handle_admin_command(chat_id, user_id, text, message)
                    return
            
            # Analyze message for spam and bad language
            result = self.detector.analyze(text, user_id, join_date)
            
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

            # Handle non-Indian language spam with immediate ban
            if result.get('immediate_ban') and result.get('non_indian_language'):
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
                
        except Exception as e:
            logger.error(f"Error handling update: {e}", exc_info=True)
    
    async def _handle_chat_member(self, chat_member: Dict):
        """Track when users join and verify suspicious accounts"""
        try:
            chat_id = chat_member.get('chat', {}).get('id')
            new_member = chat_member.get('new_chat_member', {})
            user = new_member.get('user', {})
            user_id = user.get('id')
            status = new_member.get('status')
            
            # Check if added by admin - bypass all checks
            added_by = chat_member.get('from', {})
            if added_by:
                added_by_id = added_by.get('id')
                if added_by_id and user_id != added_by_id:  # If added by someone else
                    user_is_admin = await self._is_admin(chat_id, added_by_id)
                    if user_is_admin and user.get('is_bot'):
                        logger.info(f"✨ Bot {user_id} added by admin {added_by_id}, allowing")
                        return

            if status == 'member':
                # User just joined
                member_key = f"{chat_id}_{user_id}"
                join_time = datetime.now(timezone.utc)
                self.member_join_dates[member_key] = join_time
                
                # Track join in analytics
                if self.config.ANALYTICS_ENABLED:
                    self.analytics.track_join(chat_id)
                
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
            
            elif status in ['left', 'kicked']:
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
        if self.config.AUTO_DELETE_SPAM:
            deleted = await self._delete_message(chat_id, message_id)
            if deleted:
                self.stats['messages_deleted'] += 1
                logger.info(f"🗑️ Deleted spam message from {user_name}")
        
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
                    await self._send_message(
                        chat_id,
                        f"🔨 <b>{user_name}</b> has been banned due to repeated spam violations."
                    )
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
                await self._send_message(
                    chat_id,
                    f"⚠️ <b>{user_name}</b>, your message was removed for spam. "
                    f"Warning {warnings}/{self.config.AUTO_MUTE_AFTER_WARNINGS}."
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
            
            stats_msg = f"""📊 <b>Night Watchman Stats</b>

⏱️ Uptime: {hours}h {minutes}m
📨 Messages checked: {self.stats['messages_checked']}
🚨 Spam detected: {self.stats['spam_detected']}
🗑️ Messages deleted: {self.stats['messages_deleted']}
⚠️ Users warned: {self.stats['users_warned']}
🔇 Users muted: {self.stats['users_muted']}"""
            await self._send_message(chat_id, stats_msg, auto_delete=False)
        
        elif text.startswith('/analytics'):
            # Admin-only analytics command
            await self._handle_analytics_command(chat_id, user_id, text)
        
        elif text.startswith('/rep'):
            # Show user's reputation
            if self.config.REPUTATION_ENABLED:
                msg = self.reputation.format_user_rep(user_id)
                await self._send_message(chat_id, msg, auto_delete=False)
        
        elif text.startswith('/leaderboard'):
            # Show leaderboard
            if self.config.REPUTATION_ENABLED:
                msg = self.reputation.format_leaderboard()
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
                msg = self.reputation.format_user_rep(user_id, username, user_name)
                await self._send_message(chat_id, msg)
            return True
        
        elif command == '/leaderboard':
            if self.config.REPUTATION_ENABLED:
                msg = self.reputation.format_leaderboard()
                await self._send_message(chat_id, msg)
            return True
        
        elif command == '/report':
            if self.config.REPORT_ENABLED:
                await self._handle_report(chat_id, user_id, user_name, username, message)
            return True
        
        return False  # Command not handled
    
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
            return response.json().get('ok', False)
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
        return False
    
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
    
    async def _handle_admin_command(self, chat_id: int, user_id: int, text: str, message: Dict):
        """Handle admin commands"""
        parts = text.split()
        command = parts[0].lower()
        
        # Reply to message commands
        reply_to = message.get('reply_to_message')
        target_user_id = None
        if reply_to:
            target_user_id = reply_to.get('from', {}).get('id')
        
        if command == '/warn' and target_user_id:
            warnings = self.detector.add_warning(target_user_id)
            self.stats['users_warned'] += 1

            # Track in analytics
            if self.config.ANALYTICS_ENABLED:
                self.analytics.track_warning(chat_id)
            
            target_name = reply_to.get('from', {}).get('first_name', 'User')
            await self._send_message(
                chat_id,
                f"⚠️ <b>{target_name}</b> has been warned. "
                f"Warnings: {warnings}/{self.config.AUTO_MUTE_AFTER_WARNINGS}"
            )
            
        elif command == '/ban' and target_user_id:
            banned = await self._ban_user(chat_id, target_user_id)
            if banned:
                target_name = reply_to.get('from', {}).get('first_name', 'User')
                await self._send_message(chat_id, f"🔨 <b>{target_name}</b> has been banned.")
                self.stats['users_banned'] += 1
                
        elif command == '/mute' and target_user_id:
            muted = await self._mute_user(chat_id, target_user_id)
            if muted:
                target_name = reply_to.get('from', {}).get('first_name', 'User')
                await self._send_message(
                    chat_id,
                    f"🔇 <b>{target_name}</b> has been muted for {self.config.MUTE_DURATION_HOURS}h."
                )
                self.stats['users_muted'] += 1
                
        elif command == '/unwarn' and target_user_id:
            self.detector.clear_warnings(target_user_id)
            target_name = reply_to.get('from', {}).get('first_name', 'User')
            await self._send_message(chat_id, f"✅ Warnings cleared for <b>{target_name}</b>.")
            
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
    
    async def _handle_non_indian_spam(self, chat_id: int, message_id: int, user_id: int,
                                      user_name: str, username: str, text: str, result: Dict):
        """Handle non-Indian language spam - immediate ban"""
        detected_lang = result.get('detected_language', 'unknown')
        
        logger.warning(f"🚫 Non-Indian language spam from {user_name} (@{username}): {detected_lang}")
        
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

🔨 <b>Action:</b> Banned immediately"""
            await self._send_message(self.admin_chat_id, report)
    
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
    
    async def _send_message(self, chat_id, text: str, auto_delete: bool = None) -> bool:
        """Send a message and optionally auto-delete after delay"""
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
                
                return True
            return False
        except Exception as e:
            logger.error(f"Error sending message: {e}")
        return False
    
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
