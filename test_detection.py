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
]

print('=' * 60)
print('TESTING ENHANCED DETECTION')
print('=' * 60)

for msg, expected in test_messages:
    result = detector.analyze(msg, user_id=12345)
    is_ban = result.get('instant_ban')
    status = '🚨 INSTANT BAN' if is_ban else ('⚠️ SPAM' if result.get('is_spam') else '✅ CLEAN')
    reasons = result.get('reasons', [])
    print(f'{status} [{expected}]')
    print(f'   Message: {msg[:50]}...')
    print(f'   Reasons: {reasons}')
    print()
