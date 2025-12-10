#!/usr/bin/env python3
"""Test spam detection"""
from spam_detector import SpamDetector

detector = SpamDetector()

test_messages = [
    ('💜 My х x х р о r n 💜', 'Adult/porn'),
    ('MY BEST XXX P-O-R-N', 'Adult/porn'),
    ('DM me now for profits', 'DM solicitation'),
    ('inbox me for trading', 'DM solicitation'),
    ('t.me/scambot click here', 'Telegram bot'),
    ('1win promo code get bonus', 'Casino'),
    ('Ready for big wins? promo code start cashing today', 'Promo spam'),
    # NEW: The exact spam that bypassed detection
    ('''⭐⭐⭐⭐⭐⭐⭐ ⭐⭐

⚡⚡⭐⭐ ⚡

🔥 Grаb Telegrаm Bоnus now - $200 FREE!

✅ Prоmо Сode: 200free ✅

⚡ GO! ➡ @winx (https://t.me/bonusexexbot)

🍀 Enter code 200free and set off your winning streak!

👑 Jackpot's heating up — top prize could be yours!''', 'Casino/Bot spam - MUST CATCH'),
    # Variations to test
    ('Get your winning streak started! Jackpot awaits', 'Casino keywords'),
    ('Grab your telegram bonus now!', 'Telegram bonus'),
    ('Top prize could be yours today!', 'Top prize keyword'),
]

print('=' * 60)
print('TESTING ENHANCED DETECTION')
print('=' * 60)

all_passed = True
for msg, expected in test_messages:
    result = detector.analyze(msg, user_id=12345)
    is_ban = result.get('instant_ban')
    is_spam = result.get('is_spam')
    status = '🚨 INSTANT BAN' if is_ban else ('⚠️ SPAM' if is_spam else '❌ MISSED')
    reasons = result.get('reasons', [])
    
    if not is_ban and not is_spam:
        all_passed = False
        print(f'❌ FAILED [{expected}]')
    else:
        print(f'{status} [{expected}]')
    
    print(f'   Message: {msg[:60]}...')
    print(f'   Reasons: {reasons}')
    print()

print('=' * 60)
if all_passed:
    print('✅ ALL TESTS PASSED!')
else:
    print('❌ SOME TESTS FAILED - Review above')
print('=' * 60)
