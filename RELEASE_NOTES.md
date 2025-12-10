# Release Notes

## v1.1.3 (December 10, 2025) - 🔗 Hyperlink + Emoji Detection

### New Rule
**Instant ban** for messages containing:
- Hyperlinked text (Telegram `text_link` entity)
- More than 2 emojis

### Why This Rule?
Spammers disguise malicious links behind pretty emoji-laden clickbait:
```
🔥 Click here for amazing deals! 💰🎁
```
Where "Click here" is a hidden link to a scam site. This rule catches that pattern instantly.

### Changes
- Added `entities` parameter to spam analyzer
- New `hyperlink_emoji_spam` instant-ban trigger
- Improved emoji detection pattern (better Unicode coverage)
- Extracts message entities for analysis

---

## v1.1.2 (December 10, 2025) - 📤 Forwarded Spam Detection Fix

### Critical Fix
Forwarded messages were **bypassing spam detection** because the forward handler returned early before analysis ran.

### What Was Fixed
- Forwarded messages now analyzed for spam **before** taking forward-blocking action
- If forwarded content triggers instant-ban → **immediate permanent ban** (not just mute)
- Admin reports now show when spam was forwarded

### New Instant-Ban Keywords
- `winning streak`, `top prize`, `grab bonus`, `telegram bonus`
- `enter code`, `heating up`, `could be yours`
- `$200 free`, `$100 free`, `$500 free`, `free $`

### Technical
- Deobfuscation (Cyrillic→ASCII) now applied to instant ban keyword matching
- Added `is_forwarded` flag to admin reports

---

## v1.1.1 (December 9, 2025) - 🛡️ Aggressive Anti-Spam Overhaul

### Fixed All 6 Reported Scammer Detection Failures
1. **Cyrillic-obfuscated porn** - Deobfuscates lookalikes (х→x, р→p, о→o)
2. **Aggressive DM solicitation** - Detects "DM me now", "inbox me"
3. **Emoji-obfuscated links** - Flags excessive emojis + bot links
4. **Bot account joins** - Blocks accounts by `is_bot` flag + username patterns
5. **Casino/betting promo** - Instant bans on 1win, casino keywords
6. **Forwarded spam** - Mutes on first, bans on repeat

### Instant-Ban System
Zero-tolerance violations trigger immediate permanent ban:
- Adult/porn content (normalized for obfuscation)
- Telegram bot links (t.me/botname)
- DM solicitation phrases
- Casino & betting scams
- Excessive emoji spam combinations

### Cool Ban Messages
Bot responds with entertaining ban notifications across 8 categories with sassy responses.

---

## v1.1.0 (December 8, 2025) - Initial Release

### Features
- Real-time spam detection using multiple signals
- CAS (Combot Anti-Spam) integration
- Bad language detection
- Scammer detection on join
- Anti-raid protection
- Forward blocking (VIPs exempt)
- Auto-delete spam messages
- Warn/mute/ban repeat offenders
- Reputation system with levels
- Admin commands and reports
- Analytics tracking
