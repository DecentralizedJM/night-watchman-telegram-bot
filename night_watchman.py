"""
Night Watchman - Main Bot
Telegram Spam Detection & Moderation
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
import httpx
from dotenv import load_dotenv

from config import Config
from spam_detector import SpamDetector

load_dotenv()

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
        
        # Track chat member join dates
        self.member_join_dates: Dict[str, datetime] = {}  # f"{chat_id}_{user_id}" -> datetime
        
        # Stats
        self.stats = {
            'messages_checked': 0,
            'spam_detected': 0,
            'messages_deleted': 0,
            'users_warned': 0,
            'users_muted': 0,
            'start_time': datetime.now(timezone.utc)
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
            logger.info(f"Bot: @{bot_info.get('username', 'unknown')}")
        
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
            
            # Skip messages from admins
            if await self._is_admin(chat_id, user_id):
                return
            
            self.stats['messages_checked'] += 1
            
            # Get user join date for new user detection
            member_key = f"{chat_id}_{user_id}"
            join_date = self.member_join_dates.get(member_key)
            
            # Analyze message for spam
            result = self.detector.analyze(text, user_id, join_date)
            
            if result['is_spam']:
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
        """Track when users join"""
        try:
            chat_id = chat_member.get('chat', {}).get('id')
            user_id = chat_member.get('new_chat_member', {}).get('user', {}).get('id')
            status = chat_member.get('new_chat_member', {}).get('status')
            
            if status == 'member':
                # User just joined
                member_key = f"{chat_id}_{user_id}"
                self.member_join_dates[member_key] = datetime.now(timezone.utc)
                logger.debug(f"Tracking new member: {user_id} in {chat_id}")
        except Exception as e:
            logger.error(f"Error tracking chat member: {e}")
    
    async def _handle_spam(self, chat_id: int, message_id: int, user_id: int,
                          user_name: str, username: str, text: str, result: Dict):
        """Handle detected spam"""
        self.stats['spam_detected'] += 1
        
        logger.warning(f"🚨 SPAM detected from {user_name} (@{username}): {result['reasons']}")
        
        # Delete the message
        if self.config.AUTO_DELETE_SPAM:
            deleted = await self._delete_message(chat_id, message_id)
            if deleted:
                self.stats['messages_deleted'] += 1
                logger.info(f"🗑️ Deleted spam message from {user_name}")
        
        # Warn the user
        if self.config.AUTO_WARN_USER and result['action'] == 'delete_and_warn':
            warnings = self.detector.add_warning(user_id)
            self.stats['users_warned'] += 1
            
            if warnings >= self.config.AUTO_MUTE_AFTER_WARNINGS:
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
        report = f"""🚨 <b>Spam Detected</b>

👤 User: {user_name} (@{username or 'N/A'})
🆔 User ID: <code>{user_id}</code>
💬 Chat: <code>{chat_id}</code>

📝 <b>Message:</b>
<code>{text[:500]}</code>

⚠️ <b>Reasons:</b>
{chr(10).join('• ' + r for r in result['reasons'])}

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
            await self._send_message(chat_id, welcome)
            
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
            await self._send_message(chat_id, stats_msg)
    
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
            return response.json().get('ok', False)
        except Exception as e:
            logger.error(f"Error muting user: {e}")
        return False
    
    async def _send_message(self, chat_id, text: str) -> bool:
        """Send a message"""
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML'
            }
            response = await self.client.post(url, json=data, timeout=10.0)
            return response.json().get('ok', False)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
        return False


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
