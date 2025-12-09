"""
Night Watchman - Spam Detection Engine
Analyzes messages for spam patterns
"""

import re
import logging
import hashlib
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timezone, timedelta
from config import Config

logger = logging.getLogger(__name__)


class SpamDetector:
    """Detects spam messages using multiple techniques"""
    
    def __init__(self):
        self.config = Config()
        
        # Track user message history for rate limiting
        self.user_messages: Dict[int, List[datetime]] = {}
        
        # Track duplicate messages
        self.recent_messages: Dict[str, List[int]] = {}  # message_hash -> [user_ids]
        
        # Track warnings per user
        self.user_warnings: Dict[int, int] = {}
        
        # Track forward violations for repeat detection
        self.forward_violators: Dict[int, int] = {}  # user_id -> violation_count
        
        # Cyrillic to ASCII lookalike mapping (for detecting obfuscation)
        self.cyrillic_to_ascii = {
            'а': 'a', 'А': 'A',
            'в': 'b', 'В': 'B', 
            'с': 'c', 'С': 'C',
            'е': 'e', 'Е': 'E',
            'н': 'h', 'Н': 'H',
            'і': 'i', 'І': 'I',
            'к': 'k', 'К': 'K',
            'м': 'm', 'М': 'M',
            'о': 'o', 'О': 'O',
            'р': 'p', 'Р': 'P',
            'т': 't', 'Т': 'T',
            'у': 'y', 'У': 'Y',
            'х': 'x', 'Х': 'X',
        }
        
        # Compile regex patterns
        self._compile_patterns()
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text by replacing Cyrillic lookalikes with ASCII equivalents."""
        normalized = text
        for cyrillic, ascii_char in self.cyrillic_to_ascii.items():
            normalized = normalized.replace(cyrillic, ascii_char)
        return normalized
    
    def _compile_patterns(self):
        """Compile regex patterns for efficient matching"""
        # URL pattern
        self.url_pattern = re.compile(
            r'https?://[^\s<>"{}|\\^`\[\]]+|'
            r'www\.[^\s<>"{}|\\^`\[\]]+|'
            r't\.me/[^\s<>"{}|\\^`\[\]]+'
        )
        
        # Telegram bot link pattern (instant ban)
        self.telegram_bot_pattern = re.compile(
            r't\.me/[a-zA-Z0-9_]+bot|'
            r'@[a-zA-Z0-9_]+bot',
            re.IGNORECASE
        )
        
        # Obfuscated adult content patterns
        self.adult_patterns = re.compile(
            r'x\s*x\s*x|'  # x x x
            r'p[\s\-\.]*o[\s\-\.]*r[\s\-\.]*n|'  # p-o-r-n, p.o.r.n, p o r n
            r'xxx|porn|nudes|onlyfans',
            re.IGNORECASE
        )
        
        # Crypto address patterns
        self.crypto_patterns = {
            'eth': re.compile(r'0x[a-fA-F0-9]{40}'),
            'btc': re.compile(r'[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-zA-HJ-NP-Z0-9]{39,59}'),
            'sol': re.compile(r'[1-9A-HJ-NP-Za-km-z]{32,44}'),
        }
        
        # Phone number pattern
        self.phone_pattern = re.compile(r'\+?[0-9]{10,15}')
        
        # Excessive caps pattern
        self.caps_pattern = re.compile(r'[A-Z]{5,}')
        
        # Repeated characters
        self.repeated_chars = re.compile(r'(.)\1{4,}')
    
    def analyze(self, message: str, user_id: int, user_join_date: Optional[datetime] = None) -> Dict:
        """
        Analyze a message for spam indicators
        
        Returns:
            Dict with spam score, reasons, and recommended action
        """
        result = {
            'is_spam': False,
            'spam_score': 0.0,
            'reasons': [],
            'action': 'none',
            'details': {},
            'instant_ban': False
        }
        
        if not message:
            return result
        
        message_lower = message.lower()
        # Normalize message: remove special chars for pattern matching
        message_normalized = re.sub(r'[^\w\s]', ' ', message_lower)
        message_normalized = re.sub(r'\s+', ' ', message_normalized)
        
        # 0. INSTANT BAN CHECK - Adult content, casino, aggressive DM patterns
        instant_ban_result = self._check_instant_ban(message, message_lower, message_normalized)
        if instant_ban_result['instant_ban']:
            result['is_spam'] = True
            result['instant_ban'] = True
            result['spam_score'] = 1.0
            result['action'] = 'delete_and_ban'
            result['reasons'] = instant_ban_result['reasons']
            result['details']['instant_ban_triggers'] = instant_ban_result['triggers']
            return result  # No further analysis needed
        
        # 1. Keyword detection
        keyword_score, matched_keywords = self._check_keywords(message_lower)
        if keyword_score > 0:
            result['spam_score'] += keyword_score
            result['reasons'].append(f"Spam keywords: {', '.join(matched_keywords)}")
            result['details']['keywords'] = matched_keywords
        
        # 2. URL analysis
        url_score, url_details = self._check_urls(message)
        if url_score > 0:
            result['spam_score'] += url_score
            result['reasons'].append(f"Suspicious URLs detected")
            result['details']['urls'] = url_details
        
        # 3. New user posting links
        if user_join_date:
            new_user_score = self._check_new_user(user_id, user_join_date, message)
            if new_user_score > 0:
                result['spam_score'] += new_user_score
                result['reasons'].append("New user posting links")
        
        # 4. Rate limiting check
        rate_score = self._check_rate_limit(user_id)
        if rate_score > 0:
            result['spam_score'] += rate_score
            result['reasons'].append("Sending messages too fast")
        
        # 5. Duplicate message check
        dup_score = self._check_duplicate(message, user_id)
        if dup_score > 0:
            result['spam_score'] += dup_score
            result['reasons'].append("Duplicate/repetitive message")
        
        # 6. Formatting abuse (excessive caps, emojis, etc.)
        format_score, format_reasons = self._check_formatting(message)
        if format_score > 0:
            result['spam_score'] += format_score
            result['reasons'].extend(format_reasons)
        
        # 7. Crypto address detection (often scam-related)
        crypto_score = self._check_crypto_addresses(message)
        if crypto_score > 0:
            result['spam_score'] += crypto_score
            result['reasons'].append("Contains crypto addresses")
        
        # 8. Bad language detection
        if self.config.BAD_LANGUAGE_ENABLED:
            bad_lang_score, bad_words = self._check_bad_language(message_lower)
            if bad_lang_score > 0:
                result['spam_score'] += bad_lang_score
                result['reasons'].append(f"Bad language detected: {', '.join(bad_words[:3])}")
                result['details']['bad_language'] = bad_words
                result['bad_language'] = True
        
        # 9. Non-Indian language detection (Chinese, Korean, Russian, etc.)
        if self.config.BLOCK_NON_INDIAN_LANGUAGES:
            non_indian_lang, detected_lang = self._check_non_indian_language(message)
            if non_indian_lang:
                result['non_indian_language'] = True
                result['detected_language'] = detected_lang
                result['reasons'].append(f"Non-Indian language detected: {detected_lang}")
                # Always mark for immediate action (delete or ban)
                result['spam_score'] = 1.0  # Maximum score for immediate action
                result['is_spam'] = True
                # If contains URLs/links, ban immediately. Otherwise just delete.
                if self.url_pattern.search(message):
                    result['immediate_ban'] = True
                    result['action'] = 'delete_and_ban'
                else:
                    result['action'] = 'delete_and_warn'
        
        # 10. Mention spam detection (repeated @mentions with promotional keywords)
        mention_score, mention_count = self._check_mention_spam(message)
        if mention_score > 0:
            result['spam_score'] += mention_score
            result['reasons'].append(f"Mention spam detected ({mention_count} mentions)")
            result['details']['mentions'] = mention_count
        
        # Determine if spam based on score
        if result['spam_score'] >= 0.7:
            result['is_spam'] = True
            result['action'] = 'delete_and_warn'
        elif result['spam_score'] >= 0.5:
            result['is_spam'] = True
            result['action'] = 'delete'
        elif result['spam_score'] >= 0.3:
            result['action'] = 'flag'
        
        return result
    
    def _check_instant_ban(self, message: str, message_lower: str, message_normalized: str) -> Dict:
        """
        Check for patterns that warrant INSTANT BAN (no warnings).
        These are non-negotiable violations.
        """
        result = {'instant_ban': False, 'reasons': [], 'triggers': []}
        
        # Normalize text to detect Cyrillic obfuscation (х→x, р→p, о→o, etc.)
        message_deobfuscated = self._normalize_text(message)
        message_deobfuscated_lower = message_deobfuscated.lower()
        
        # 1. Adult/Porn content (obfuscated or not)
        # Check both original and deobfuscated versions
        if self.adult_patterns.search(message) or self.adult_patterns.search(message_deobfuscated):
            result['instant_ban'] = True
            result['reasons'].append("Adult/porn content detected")
            result['triggers'].append("adult_content")
            return result
        
        # 2. Telegram bot links (scam bots)
        if self.telegram_bot_pattern.search(message):
            result['instant_ban'] = True
            result['reasons'].append("Telegram bot link detected")
            result['triggers'].append("telegram_bot_link")
            return result
        
        # 3. Casino/Betting/Promo code spam
        casino_keywords = ['1win', 'casino', 'promo code', 'welcome bonus', 'big wins', 
                          'jackpot', 'free spins', 'betting', 'slot machine']
        for keyword in casino_keywords:
            if keyword in message_lower or keyword in message_deobfuscated_lower:
                result['instant_ban'] = True
                result['reasons'].append(f"Casino/betting spam detected: {keyword}")
                result['triggers'].append("casino_spam")
                return result
        
        # 4. Aggressive DM patterns (instant ban)
        dm_patterns = ['dm me now', 'inbox me', 'message me now', 'dm me', 
                       'aaja inbox', 'inbox karo', 'dm kar', 'dm karo']
        for pattern in dm_patterns:
            if pattern in message_lower or pattern in message_normalized:
                result['instant_ban'] = True
                result['reasons'].append(f"Aggressive DM solicitation: {pattern}")
                result['triggers'].append("dm_solicitation")
                return result
        
        # 5. Check for instant ban keywords from config
        if hasattr(self.config, 'INSTANT_BAN_KEYWORDS'):
            for keyword in self.config.INSTANT_BAN_KEYWORDS:
                if keyword.lower() in message_lower or keyword.lower() in message_normalized:
                    result['instant_ban'] = True
                    result['reasons'].append(f"Instant ban keyword: {keyword}")
                    result['triggers'].append("instant_ban_keyword")
                    return result
        
        # 6. Emoji-heavy messages with links (obfuscation pattern)
        emoji_count = len(re.findall(r'[\U0001F300-\U0001F9FF]', message))
        has_links = bool(self.url_pattern.search(message))
        if emoji_count > 10 and has_links:
            # Check for promotional keywords
            promo_keywords = ['right here', 'click', 'join', 'bonus', 'win', 'free']
            for keyword in promo_keywords:
                if keyword in message_lower:
                    result['instant_ban'] = True
                    result['reasons'].append("Emoji-obfuscated spam with links")
                    result['triggers'].append("emoji_obfuscation")
                    return result
        
        return result
    
    def _check_keywords(self, message: str) -> Tuple[float, List[str]]:
        """Check for spam keywords"""
        matched = []
        for keyword in self.config.SPAM_KEYWORDS:
            if keyword.lower() in message:
                matched.append(keyword)
        
        if len(matched) >= 3:
            return 0.8, matched
        elif len(matched) >= 2:
            return 0.5, matched
        elif len(matched) >= 1:
            return 0.3, matched
        return 0.0, []
    
    def _check_urls(self, message: str) -> Tuple[float, Dict]:
        """Check for suspicious URLs"""
        urls = self.url_pattern.findall(message)
        details = {'found': urls, 'suspicious': [], 'whitelisted': []}
        
        if not urls:
            return 0.0, details
        
        score = 0.0
        for url in urls:
            url_lower = url.lower()
            
            # Check whitelist first
            is_whitelisted = any(domain in url_lower for domain in self.config.WHITELISTED_DOMAINS)
            if is_whitelisted:
                details['whitelisted'].append(url)
                continue
            
            # Check suspicious domains
            is_suspicious = any(domain in url_lower for domain in self.config.SUSPICIOUS_DOMAINS)
            if is_suspicious:
                details['suspicious'].append(url)
                score += 0.4
            else:
                # Unknown external link
                score += 0.2
        
        return min(score, 0.8), details
    
    def _check_new_user(self, user_id: int, join_date: datetime, message: str) -> float:
        """Check if new user is posting links"""
        now = datetime.now(timezone.utc)
        hours_in_group = (now - join_date).total_seconds() / 3600
        
        if hours_in_group < self.config.NEW_USER_LINK_BLOCK_HOURS:
            # New user - check if they're posting links
            if self.url_pattern.search(message):
                return 0.6
        return 0.0
    
    def _check_rate_limit(self, user_id: int) -> float:
        """Check if user is sending too many messages"""
        now = datetime.now(timezone.utc)
        one_minute_ago = now - timedelta(minutes=1)
        
        # Clean old messages
        if user_id in self.user_messages:
            self.user_messages[user_id] = [
                t for t in self.user_messages[user_id] if t > one_minute_ago
            ]
        else:
            self.user_messages[user_id] = []
        
        # Add current message
        self.user_messages[user_id].append(now)
        
        count = len(self.user_messages[user_id])
        if count > self.config.MAX_MESSAGES_PER_MINUTE:
            return 0.5
        elif count > self.config.MAX_MESSAGES_PER_MINUTE * 0.7:
            return 0.2
        return 0.0
    
    def _check_duplicate(self, message: str, user_id: int) -> float:
        """Check for duplicate messages (spam floods)"""
        # Use SHA256 hash for consistent message hashing
        msg_hash = hashlib.sha256(message.lower().strip().encode()).hexdigest()
        
        if msg_hash not in self.recent_messages:
            self.recent_messages[msg_hash] = []
        
        self.recent_messages[msg_hash].append(user_id)
        
        # Clean old entries (keep last 100)
        if len(self.recent_messages) > 100:
            oldest_key = next(iter(self.recent_messages))
            del self.recent_messages[oldest_key]
        
        count = len(self.recent_messages[msg_hash])
        if count >= self.config.DUPLICATE_MESSAGE_THRESHOLD:
            return 0.6
        return 0.0
    
    def _check_formatting(self, message: str) -> Tuple[float, List[str]]:
        """Check for spam-like formatting"""
        score = 0.0
        reasons = []
        
        # Excessive caps
        caps_matches = self.caps_pattern.findall(message)
        if len(caps_matches) >= 3:
            score += 0.3
            reasons.append("Excessive caps")
        
        # Repeated characters
        if self.repeated_chars.search(message):
            score += 0.2
            reasons.append("Repeated characters")
        
        # Too many emojis (crude check)
        emoji_count = len(re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF]', message))
        if emoji_count > 10:
            score += 0.2
            reasons.append("Excessive emojis")
        
        return score, reasons
    
    def _check_crypto_addresses(self, message: str) -> float:
        """Check for crypto addresses (often posted by scammers)"""
        for name, pattern in self.crypto_patterns.items():
            if pattern.search(message):
                return 0.4
        return 0.0
    
    def _check_mention_spam(self, message: str) -> Tuple[float, int]:
        """Check for mention spam pattern (e.g., @channel @channel @channel + promotional text)
        
        Detects bot/spam behavior like:
        @somechannel @somechannel @somechannel 
        Join now 
        hyperlink
        """
        # Find all @mentions
        mention_pattern = r'@[\w]+'
        mentions = re.findall(mention_pattern, message)
        mention_count = len(mentions)
        
        # Check if message has promotional/spam keywords
        spam_keywords = ['join', 'click', 'now', 'link', 'hurry', 'act', 'fast', "don't miss"]
        has_promo = any(keyword in message.lower() for keyword in spam_keywords)
        
        # Scoring logic:
        score = 0.0
        
        # 3+ mentions is suspicious
        if mention_count >= 5:
            score = 0.7  # High confidence spam
        elif mention_count >= 3:
            if has_promo:
                score = 0.6  # Strong spam signal
            else:
                score = 0.3  # Moderate suspicion
        elif mention_count >= 2:
            if has_promo:
                score = 0.4  # Mention spam with promo
        
        # Check for duplicate mentions (same @channel multiple times)
        unique_mentions = len(set(mentions))
        if mention_count > 0 and unique_mentions < mention_count * 0.5:
            # Many duplicates = definitely spam
            score = max(score, 0.5)
        
        return score, mention_count
    
    def add_warning(self, user_id: int) -> int:
        """Add warning to user, return total warnings"""
        self.user_warnings[user_id] = self.user_warnings.get(user_id, 0) + 1
        return self.user_warnings[user_id]
    
    def get_warnings(self, user_id: int) -> int:
        """Get warning count for user"""
        return self.user_warnings.get(user_id, 0)
    
    def clear_warnings(self, user_id: int):
        """Clear warnings for user"""
        if user_id in self.user_warnings:
            del self.user_warnings[user_id]
    
    def _check_non_indian_language(self, message: str) -> Tuple[bool, str]:
        """Check if message contains non-Indian languages (Chinese, Korean, Russian, etc.)
        
        Note: Hindi (Devanagari), Tamil, Telugu, Bengali, etc. are ALLOWED as Indian languages.
        """
        if not self.config.BLOCK_NON_INDIAN_LANGUAGES:
            return False, ""
        
        # Unicode ranges for BLOCKED non-Indian languages
        language_ranges = {
            'chinese': [
                (0x4E00, 0x9FFF),  # CJK Unified Ideographs
                (0x3400, 0x4DBF),  # CJK Extension A
                (0x20000, 0x2A6DF),  # CJK Extension B
            ],
            'korean': [
                (0xAC00, 0xD7A3),  # Hangul Syllables
                (0x1100, 0x11FF),  # Hangul Jamo
            ],
            'russian': [
                (0x0400, 0x04FF),  # Cyrillic
            ],
            'japanese': [
                (0x3040, 0x309F),  # Hiragana
                (0x30A0, 0x30FF),  # Katakana
            ],
            'arabic': [
                (0x0600, 0x06FF),  # Arabic
            ],
            'thai': [
                (0x0E00, 0x0E7F),  # Thai
            ],
            'vietnamese': [
                (0x1EA0, 0x1EFF),  # Vietnamese Extended
            ],
        }
        
        # Indian languages (ALLOWED - Devanagari, Tamil, Telugu, Bengali, etc.)
        # 0x0900-0x097F: Devanagari (Hindi, Marathi, Sanskrit)
        # 0x0980-0x09FF: Bengali
        # 0x0A00-0x0A7F: Gurmukhi (Punjabi)
        # 0x0A80-0x0AFF: Gujarati
        # 0x0B00-0x0B7F: Oriya
        # 0x0B80-0x0BFF: Tamil
        # 0x0C00-0x0C7F: Telugu
        # 0x0C80-0x0CFF: Kannada
        # 0x0D00-0x0D7F: Malayalam
        
        detected_languages = []
        for lang, ranges in language_ranges.items():
            for start, end in ranges:
                if any(start <= ord(char) <= end for char in message):
                    detected_languages.append(lang)
                    break
        
        if detected_languages:
            return True, ', '.join(detected_languages)
        
        return False, ""
    
    def _check_bad_language(self, message: str) -> Tuple[float, List[str]]:
        """Check for bad language/profanity"""
        if not self.config.BAD_LANGUAGE_ENABLED:
            return 0.0, []
        
        found_words = []
        message_lower = message.lower()
        
        for word in self.config.BAD_LANGUAGE_WORDS:
            # Check for whole word matches (with word boundaries)
            pattern = r'\b' + re.escape(word.lower()) + r'\b'
            if re.search(pattern, message_lower):
                found_words.append(word)
        
        if len(found_words) >= 3:
            return 0.6, found_words
        elif len(found_words) >= 2:
            return 0.4, found_words
        elif len(found_words) >= 1:
            return 0.3, found_words
        
        return 0.0, []
    
    def add_forward_violation(self, user_id: int) -> int:
        """
        Track forward violations for a user.
        Returns the violation count.
        """
        if user_id not in self.forward_violators:
            self.forward_violators[user_id] = 0
        self.forward_violators[user_id] += 1
        return self.forward_violators[user_id]
    
    def get_forward_violations(self, user_id: int) -> int:
        """Get forward violation count for a user."""
        return self.forward_violators.get(user_id, 0)
    
    def clear_forward_violations(self, user_id: int):
        """Clear forward violations for a user."""
        if user_id in self.forward_violators:
            del self.forward_violators[user_id]