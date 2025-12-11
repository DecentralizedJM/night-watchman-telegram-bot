# 🌙 Night Watchman Bot - Debugging Report

**Generated:** December 11, 2025  
**Repository:** `DecentralizedJM/night-watchman-telegram-bot`  
**Branch:** `main`

---

## 📋 Executive Summary

The Night Watchman bot is a Telegram spam detection and moderation bot with ~2,100 lines of core code. Overall the code is well-structured but has several bugs, potential issues, and areas for improvement.

---

## 🐛 BUGS (Critical - Should Fix)

### 1. ✅ FIXED: `/rep` in DM Shows Admin Message to Everyone
- **Location:** `night_watchman.py` lines 1125-1131 (was)
- **Issue:** `_handle_private_message` responded "You're an admin!" to ALL users using `/rep` in DM
- **Status:** Fixed in commit `3d27e54`

### 2. ⚠️ Memory Leak: `message_authors` Dict Grows Unbounded
- **Location:** `night_watchman.py` line 78, 308
- **Issue:** `self.message_authors` stores message author mappings forever
- **Impact:** Memory grows over time, potential crash on long-running instances
- **Fix:** Add cleanup mechanism or use TTL cache

```python
# Current (problematic)
self.message_authors: Dict[str, int] = {}  # Never cleaned up

# Suggested fix - add to _handle_update or periodic cleanup
if len(self.message_authors) > 10000:
    # Keep only recent 5000 entries
    self.message_authors = dict(list(self.message_authors.items())[-5000:])
```

### 3. ⚠️ Memory Leak: `enhanced_messages` Dict Grows Unbounded
- **Location:** `night_watchman.py` line 83
- **Issue:** `self.enhanced_messages` tracks enhanced messages forever
- **Same fix needed as above**

### 4. ⚠️ Memory Leak: `recent_joins` Dict Cleanup Incomplete
- **Location:** `night_watchman.py` lines 808-812
- **Issue:** Cleans old timestamps but never removes empty chat entries
- **Fix:** Remove empty chat_id keys after cleanup

### 5. ⚠️ `_parse_target_from_command` Method Missing
- **Location:** Referenced in `night_watchman.py` lines 1580, 1596, 1614, etc.
- **Issue:** Method is called but not defined in the file
- **Impact:** Admin commands `/warn`, `/ban`, `/mute` with @username won't work properly
- **Fix:** Implement the missing method

### 6. ⚠️ Duplicate Admin Check on Every Message
- **Location:** `night_watchman.py` lines 347-360
- **Issue:** `_is_admin()` called multiple times per message (lines 333, 342, 349, 356)
- **Impact:** Unnecessary API calls, potential rate limiting
- **Fix:** Cache admin check result at start of `_handle_update`

### 7. ⚠️ Race Condition in Daily Activity Tracking
- **Location:** `reputation_tracker.py` lines 143-165
- **Issue:** Check-then-add pattern without locking can cause duplicate point awards
- **Impact:** Minor - users might occasionally get double points

---

## ⚡ PERFORMANCE ISSUES

### 1. Synchronous File I/O in Hot Path
- **Location:** `reputation_tracker.py` and `analytics_tracker.py`
- **Issue:** `_save_data()` writes to disk on EVERY event (message, join, etc.)
- **Impact:** Slow response time, disk I/O bottleneck
- **Fix:** 
  - Use async file I/O
  - Batch writes (save every N seconds instead of every event)
  - Use SQLite instead of JSON

### 2. No Caching of Admin Status
- **Location:** `night_watchman.py` line 1305
- **Issue:** Every `_is_admin()` call makes an API request
- **Fix:** Cache admin list per chat with TTL (e.g., 5 minutes)

```python
# Suggested implementation
self.admin_cache: Dict[int, Tuple[List[int], datetime]] = {}  # chat_id -> (admin_ids, expiry)

async def _is_admin(self, chat_id: int, user_id: int) -> bool:
    now = datetime.now(timezone.utc)
    if chat_id in self.admin_cache:
        admin_ids, expiry = self.admin_cache[chat_id]
        if now < expiry:
            return user_id in admin_ids
    # Fetch and cache
    admins = await self._get_chat_admins(chat_id)
    admin_ids = [a['user'].get('id') for a in admins]
    self.admin_cache[chat_id] = (admin_ids, now + timedelta(minutes=5))
    return user_id in admin_ids
```

### 3. Regex Compilation on Every Message
- **Location:** `spam_detector.py` line 419
- **Issue:** Emoji patterns compiled inline: `len(re.findall(...))`
- **Fix:** Already pre-compiled in `_compile_patterns()` but not always used

---

## 🔒 SECURITY CONCERNS

### 1. No Input Validation on User IDs
- **Location:** Admin commands parsing
- **Issue:** User IDs from text parsing aren't validated
- **Risk:** Low - Telegram API would reject invalid IDs anyway

### 2. HTML Injection in Messages
- **Location:** Multiple places where user names are embedded in HTML
- **Issue:** User names with `<script>` or HTML tags could break formatting
- **Fix:** Escape HTML entities in user-provided content

```python
import html
user_name_safe = html.escape(user_name)
```

### 3. Sensitive Data in Logs
- **Location:** Throughout logging statements
- **Issue:** User IDs and usernames logged extensively
- **Risk:** Low - but consider GDPR implications

---

## 🧹 CODE QUALITY ISSUES

### 1. Inconsistent Command Matching
- **Location:** `night_watchman.py`
- **Issue:** Mix of `.startswith('/rep')` and `.split()[0].lower() == '/rep'`
- **Impact:** `/repblah` would match with `startswith` but not with split
- **Fix:** Standardize to split approach

### 2. Magic Numbers
- **Location:** Throughout config
- **Issue:** Many hardcoded values could be constants
- **Example:** `60` seconds for auto-delete, `5000` for cache size

### 3. Error Handling Swallows Exceptions
- **Location:** Multiple `try/except` blocks return `False` or `{}`
- **Issue:** Errors are logged but not properly handled
- **Impact:** Silent failures hard to debug

### 4. Duplicate Code in Admin Commands
- **Location:** `night_watchman.py` lines 1555-1680
- **Issue:** `/warn`, `/ban`, `/mute`, `/unwarn` have nearly identical structure
- **Fix:** Extract common pattern to helper method

### 5. Inconsistent Async Patterns
- **Location:** `asyncio.create_task()` without error handling
- **Issue:** Lines 1706, 1710 create tasks but never await or handle errors
- **Fix:** Add error callbacks or use `asyncio.gather()`

---

## 📊 FEATURE GAPS

### 1. No Persistence of In-Memory State
- **Issue:** `user_warnings`, `forward_violators`, `media_timestamps` lost on restart
- **Impact:** Users can bypass warning limits by waiting for bot restart
- **Fix:** Persist to file/database

### 2. No Graceful Shutdown
- **Issue:** Bot doesn't save state on SIGINT/SIGTERM
- **Fix:** Add signal handlers

### 3. Missing `/unban` Command
- **Issue:** Can ban but not unban users via command
- **Fix:** Add `/unban` admin command

### 4. No Rate Limiting on Bot API Calls
- **Issue:** Heavy load could hit Telegram rate limits
- **Fix:** Implement exponential backoff

---

## 🧪 TESTING GAPS

### 1. No Unit Tests for Core Logic
- **Status:** `tests/test_spam_detection.py` exists but is integration-style
- **Missing:** Unit tests for edge cases, mocking, etc.

### 2. No Tests for Admin Commands
- **Missing:** Test coverage for `/ban`, `/mute`, `/warn`, etc.

### 3. No Tests for Analytics
- **Missing:** Test coverage for `AnalyticsTracker`

---

## 📝 RECOMMENDATIONS (Priority Order)

### High Priority
1. ✅ Fix memory leaks in `message_authors` and `enhanced_messages`
2. ✅ Implement missing `_parse_target_from_command` method
3. ✅ Cache admin status to reduce API calls
4. ✅ Add HTML escaping for user input

### Medium Priority
5. Batch file writes in analytics/reputation trackers
6. Persist warning counts across restarts
7. Add graceful shutdown handler
8. Standardize command matching pattern

### Low Priority
9. Add `/unban` command
10. Improve test coverage
11. Add rate limiting for API calls
12. Refactor duplicate admin command code

---

## 📁 FILE SUMMARY

| File | Lines | Purpose | Issues |
|------|-------|---------|--------|
| `night_watchman.py` | 2,095 | Main bot | Memory leaks, duplicate API calls |
| `spam_detector.py` | 767 | Spam detection | Well-structured ✅ |
| `reputation_tracker.py` | 435 | Reputation system | Sync I/O, race conditions |
| `analytics_tracker.py` | 376 | Analytics | Sync I/O |
| `config.py` | 405 | Configuration | Well-structured ✅ |

---

## ✅ WHAT'S WORKING WELL

1. **Comprehensive spam detection** - Multi-layered approach with keywords, patterns, rate limiting
2. **Good logging** - Detailed logging throughout
3. **Modular design** - Separate classes for different concerns
4. **Configurable** - Almost everything is configurable via `Config` class
5. **Multiple language support** - Hindi/Hinglish profanity detection
6. **CAS integration** - Combot Anti-Spam database check
7. **Reputation system** - Well-designed points and levels

---

*Report generated by Claude / GitHub Copilot*
