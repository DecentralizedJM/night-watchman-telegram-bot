#!/usr/bin/env python3
"""Debug spam detection failure"""
from spam_detector import SpamDetector
import re

detector = SpamDetector()

# The exact spam message that bypassed
spam_msg = """2⃣2⃣🕚💰  ⚡ 🎭👺👹🧑‍🦲🦷

📣 play anywhere, anytime! 

➡ @xwin (https://t.me/NEWPROMOCASBOT) ⬅

😆 Activate the promo code BET220 and get $220 on your balance!"""

result = detector.analyze(spam_msg, user_id=12345)
print('Spam Message Analysis:')
print('=' * 60)
print(f'Is Spam: {result.get("is_spam")}')
print(f'Instant Ban: {result.get("instant_ban")}')
print(f'Spam Score: {result.get("spam_score")}')
print(f'Action: {result.get("action")}')
print(f'Reasons: {result.get("reasons")}')
print()

# Check bot pattern - current pattern
bot_pattern = re.compile(r't\.me/[a-zA-Z0-9_]+bot', re.IGNORECASE)
test_url = "https://t.me/NEWPROMOCASBOT"
print(f'Current bot pattern match on "{test_url}": {bool(bot_pattern.search(test_url))}')

# The issue: pattern expects "bot" at END, but NEWPROMOCASBOT has "BOT" at end
# Let's check if it's case sensitivity or pattern issue
print(f'Does "NEWPROMOCASBOT" end with "bot" (case insensitive)? {test_url.lower().endswith("bot")}')

# Check what keywords match
msg_lower = spam_msg.lower()
keywords = ['promo code', 'activate', 'balance', 'play', 'casino', 'bet', 'win']
print('\nKeyword matches:')
for kw in keywords:
    if kw in msg_lower:
        print(f'  ✓ Found: {kw}')
    else:
        print(f'  ✗ Not found: {kw}')
