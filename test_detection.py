#!/usr/bin/env python3
"""Test spam detection"""
from spam_detector import SpamDetector

detector = SpamDetector()

# Messages that SHOULD be detected as spam/instant ban
spam_messages = [
    ('💜 My х x х р о r n 💜', 'Adult/porn', None),
    ('MY BEST XXX P-O-R-N', 'Adult/porn', None),
    ('DM me now for profits', 'DM solicitation', None),
    ('inbox me for trading', 'DM solicitation', None),
    ('t.me/scambot click here', 'Telegram bot', None),
    ('1win promo code get bonus', 'Casino - 1win', None),
    ('Ready for big wins? promo code start cashing today', 'Promo spam with signals', None),
    # The exact spam that bypassed detection previously
    ('''⭐⭐⭐⭐⭐⭐⭐ ⭐⭐

⚡⚡⭐⭐ ⚡

🔥 Grаb Telegrаm Bоnus now - $200 FREE!

✅ Prоmо Сode: 200free ✅

⚡ GO! ➡ @winx (https://t.me/bonusexexbot)

🍀 Enter code 200free and set off your winning streak!

👑 Jackpot's heating up — top prize could be yours!''', 'Casino/Bot spam - MUST CATCH', None),
    # NEW spam pattern from Issue 1
    ('''2⃣2⃣🕚💰  ⚡ 🎭👺👹🧑‍🦲🦷

📣 play anywhere, anytime! 

➡ @xwin ⬅

😆 Activate the promo code BET220 and get $220 on your balance!''', 'xwin/BET220 spam - MUST CATCH', None),
    # Variations to test
    ('Get your winning streak started! Jackpot awaits', 'Casino keywords', None),
    ('Grab your telegram bonus now!', 'Telegram bonus', None),
    ('Top prize could be yours today!', 'Top prize keyword', None),
    # Hyperlink + emoji test
    ('🔥 Click here for amazing deals! 💰🎁', 'Hyperlink + emojis', [{'type': 'text_link', 'url': 'https://scam.com'}]),
    ('Check this out ✨🌟⭐', 'Hyperlink + 3 emojis', [{'type': 'text_link', 'url': 'https://spam.com'}]),
]

# Messages that should NOT be detected as spam (legitimate questions)
safe_messages = [
    ('How to get promo codes in Mudrex', 'Legit question about Mudrex promo'),
    ('Is there any promo code for mudrex?', 'Legit promo question'),
    ('Where can I find Mudrex referral code?', 'Legit referral question'),
    ('What is the best trading strategy?', 'Normal question'),
    ('Can someone help me with my withdrawal?', 'Support question'),
    ('mudrex promo code kahan milega?', 'Hindi promo question'),
]

# Money emoji tests - should be caught for NEW/LOW-REP users only
money_emoji_tests = [
    # (message, expected_desc, user_rep, is_first_message, should_be_spam)
    ('💰💰 Make money fast! 💵💵💵', 'Money spam from new user', 0, True, True),
    ('Get rich 💸💸💸 with this method!', 'Money spam from 0-rep user', 0, False, True),
    ('🤑🤑 Easy profits await you!', 'Money spam first message', 0, True, True),
    ('Thanks for the help! 💰', 'Single money emoji - trusted user', 10, False, False),  # Should be SAFE
    ('Made some good trades today 💵💵', 'Money emojis from trusted user', 50, False, False),  # Should be SAFE
]

print('=' * 60)
print('TESTING SPAM DETECTION (Should be CAUGHT)')
print('=' * 60)

all_passed = True
for item in spam_messages:
    msg, expected, entities = item
    result = detector.analyze(msg, user_id=12345, entities=entities)
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
print('TESTING SAFE MESSAGES (Should NOT be caught)')
print('=' * 60)

for msg, expected in safe_messages:
    result = detector.analyze(msg, user_id=12345, entities=None)
    is_ban = result.get('instant_ban')
    is_spam = result.get('is_spam')
    
    if is_ban or is_spam:
        all_passed = False
        status = '❌ FALSE POSITIVE - BANNED!' if is_ban else '❌ FALSE POSITIVE - SPAM'
        print(f'{status} [{expected}]')
        print(f'   Message: {msg}')
        print(f'   Reasons: {result.get("reasons", [])}')
    else:
        print(f'✅ SAFE [{expected}]')
        print(f'   Message: {msg}')
    print()

print('=' * 60)
print('TESTING MONEY EMOJI DETECTION')
print('=' * 60)

from datetime import datetime, timezone, timedelta

for msg, expected, user_rep, is_first_msg, should_be_spam in money_emoji_tests:
    # For new/low-rep users: joined 1 hour ago
    # For trusted users: joined 30 days ago
    if user_rep >= 10:
        join_date = datetime.now(timezone.utc) - timedelta(days=30)
    else:
        join_date = datetime.now(timezone.utc) - timedelta(hours=1)
    
    result = detector.analyze(
        msg, user_id=99999, 
        user_join_date=join_date, 
        entities=None,
        user_rep=user_rep,
        is_first_message=is_first_msg
    )
    is_spam = result.get('is_spam')
    
    if should_be_spam:
        if is_spam:
            print(f'🚨 CAUGHT [{expected}]')
            print(f'   Message: {msg}')
            print(f'   Reasons: {result.get("reasons", [])}')
        else:
            all_passed = False
            print(f'❌ MISSED [{expected}]')
            print(f'   Message: {msg}')
    else:
        if is_spam:
            all_passed = False
            print(f'❌ FALSE POSITIVE [{expected}]')
            print(f'   Message: {msg}')
            print(f'   Reasons: {result.get("reasons", [])}')
        else:
            print(f'✅ SAFE [{expected}]')
            print(f'   Message: {msg}')
    print()

print('=' * 60)
if all_passed:
    print('✅ ALL TESTS PASSED!')
else:
    print('❌ SOME TESTS FAILED - Review above')
print('=' * 60)
