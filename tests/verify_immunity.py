
import asyncio
import logging
from unittest.mock import MagicMock, AsyncMock
from night_watchman import NightWatchman
from reputation_tracker import ReputationTracker
from config import Config

# Setup Mock Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import os
os.environ['TELEGRAM_BOT_TOKEN'] = "123:dummy_token"

from night_watchman import NightWatchman

async def test_immunity():
    print("🧪 Starting Immunity Verification Check...")
    
    # 1. Setup Mock Bot
    bot = NightWatchman()
    bot.client = AsyncMock()
    bot._send_message = AsyncMock()
    bot._delete_message = AsyncMock(return_value=True)
    bot._ban_user = AsyncMock(return_value=True)
    bot.detector.learn_spam = MagicMock()
    
    # 2. Setup Mock Reputation
    bot.reputation = ReputationTracker()
    bot.reputation.data = {'users': {}} # Reset data
    bot.reputation._save_data = MagicMock() 
    
    # helper to create user
    def set_user_points(user_id, points, enhanced=False):
        key = str(user_id)
        bot.reputation.data['users'][key] = {
            'points': points,
            'is_admin_enhanced': enhanced
        }

    # Test Case 1: Low Rep User (Should be BANNED)
    print("\n[Test 1] Low Rep User (Points: 5) sends Scam")
    set_user_points(101, 5)
    
    result = {
        'instant_ban': True, 
        'spam_score': 8.5, 
        'reasons': ['Recruitment Scam'],
        'triggers': ['recruitment_scam'],
        'details': {'instant_ban_triggers': ['recruitment_scam']}
    }
    
    await bot._handle_instant_ban(
        chat_id=-1001, message_id=1, user_id=101, 
        user_name="LowRep", username="lowrep", 
        text="Scam message", result=result
    )
    
    if bot._ban_user.call_count == 1:
        print("✅ PASS: Low rep user was BANNED")
    else:
        print("❌ FAIL: Low rep user was NOT banned")
        
    bot._ban_user.reset_mock()
    bot._send_message.reset_mock()

    # Test Case 2: High Rep User (Should be SPARED)
    print("\n[Test 2] High Rep User (Points: 50) sends Scam")
    set_user_points(102, 50)
    
    await bot._handle_instant_ban(
        chat_id=-1001, message_id=2, user_id=102, 
        user_name="HighRep", username="highrep", 
        text="Scam message", result=result
    )
    
    if bot._ban_user.call_count == 0:
        print("✅ PASS: High rep user was SPARED (Not Banned)")
        # Check if warning sent
        args, _ = bot._send_message.call_args
        if "High reputation saved you" in args[1]:
            print("✅ PASS: Warning message sent")
    else:
        print("❌ FAIL: High rep user was BANNED")

    bot._ban_user.reset_mock()
    bot._send_message.reset_mock()

    # Test Case 3: Enhanced User (Points: 0) sends Scam
    print("\n[Test 3] Admin Enhanced User (Points: 0) sends Scam")
    set_user_points(103, 0, enhanced=True)
    
    await bot._handle_instant_ban(
        chat_id=-1001, message_id=3, user_id=103, 
        user_name="Enhanced", username="enhanced", 
        text="Scam message", result=result
    )

    if bot._ban_user.call_count == 0:
         print("✅ PASS: Enhanced user was SPARED")
    else:
         print("❌ FAIL: Enhanced user was BANNED")

    bot._ban_user.reset_mock()
    bot._send_message.reset_mock()

    # Test Case 4: High Rep User sends "Very Severe" content (Should be BANNED)
    print("\n[Test 4] High Rep User (Points: 50) sends ADULT CONTENT")
    set_user_points(102, 50)
    
    severe_result = {
        'instant_ban': True, 
        'spam_score': 1.0, 
        'reasons': ['Adult Content'],
        'triggers': ['adult_content'], # This triggers the override
        'details': {'instant_ban_triggers': ['adult_content']}
    }
    
    await bot._handle_instant_ban(
        chat_id=-1001, message_id=4, user_id=102, 
        user_name="HighRep", username="highrep", 
        text="Adult content", result=severe_result
    )
    
    if bot._ban_user.call_count == 1:
         print("✅ PASS: High rep user was BANNED for Very Severe violation")
    else:
         print("❌ FAIL: High rep user was SPARED for Very Severe violation")

if __name__ == "__main__":
    asyncio.run(test_immunity())
