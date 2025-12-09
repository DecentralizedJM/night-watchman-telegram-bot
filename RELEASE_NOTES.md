# Release Notes

## v1.1.0 - 🛡️ Aggressive Anti-Spam Overhaul (December 9, 2025)

### 🎯 Fixed All 6 Reported Scammer Detection Failures

#### Detection Enhancements:
- **Cyrillic Deobfuscation**: Automatically normalize Cyrillic lookalikes (х→x, р→p, о→o) to catch obfuscated porn messages
- **Instant-Ban System**: Zero-tolerance for 7 violation categories (adult content, DM solicitation, bot links, casino promo, excessive emoji spam)
- **Forward Violation Tracking**: Escalating penalties - 1st forward = mute, repeat = permanent ban
- **Bot Account Blocking**: Detect and remove bot accounts by is_bot flag + username patterns
- **Excessive Emoji Detection**: Flag messages with >8 emojis + links or >15 emojis + casino keywords

#### 🎭 Cool Ban Messages
The bot now responds with sassy, entertaining ban notifications across 8 categories:
- Scammer alerts: *"🚨 Scammer alert! {name} just got yeeted! 👋"*
- Bot termination: *"🤖 Nice try, bot! {name} has been terminated. 🔌"*
- Forward violations: *"📨 No forwarding allowed! {name} learns the hard way. 🎓"*
- Casino spam: *"🎰 No gambling spam here! Taking out the trash. 🗑️"*
- And 4 more entertaining categories!

### ✅ Test Coverage
All 6 reported cases now trigger instant bans:
1. ✅ Cyrillic-obfuscated porn messages
2. ✅ Aggressive DM solicitation
3. ✅ Emoji-obfuscated Telegram bot links
4. ✅ Bot account joins
5. ✅ Casino/betting promo spam
6. ✅ Forwarded spam messages

### 📝 Files Modified
- `spam_detector.py`: Added deobfuscation, instant-ban detection, forward tracking
- `config.py`: Added 40+ instant-ban keywords, bot blocking config
- `night_watchman.py`: Updated all ban notifications with cool message templates
- `test_detection.py`: New comprehensive test suite for all 6 cases

### 🚀 Deployment
Ready for production deployment to Railway. All test cases verified.

---

## v1.0.0 - Initial Release
Initial deployment with core moderation features, CAS API integration, and reputation tracking.
