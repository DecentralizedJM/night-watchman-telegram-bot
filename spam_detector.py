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

# Import ML classifier (optional - gracefully degrades if not available)
try:
    from ml_classifier import get_classifier, SpamClassifier
    ML_ENABLED = True
except ImportError:
    ML_ENABLED = False

logger = logging.getLogger(__name__)


class SpamDetector:
    def _check_flexible_scam_patterns(self, message: str, message_lower: str) -> Dict:
        """
        Detect scam patterns using regex and partial phrase matching for broader coverage.
        """
        result = {'instant_ban': False, 'reasons': [], 'triggers': []}
        scam_regexes = [
            r"thanks to [^,\n]+,? my (trading )?account is (thriving|growing|doing great)",
            r"profit (with|thanks to) (mrs|mr|@)[^\s]+",
            r"withdrawals? (are|is) (easy|straightforward|simple|without hassle)",
            r"from [^\n]+ to \$?\d{2,5} (profit|returns|income)",
            r"automated trading system (based on|using) (market conditions|algorithms)",
            r"avoids? risky strategies? (like|such as) (martingale|grid|hedging)",
            r"aims? for a daily (performance|return|roi|profit) of ?\d+%?",
            r"(ea|system) operates? on the m\d+ timeframe",
            r"compatible with all brokers",
            r"manages? (sl/tp|stop loss|take profit)",
            r"works 24/5 on mt4( and mt5)?",
            r"funded account challenges?",
            r"send me a dm (for|to see|for more) (proof|results|details)",
            r"financial assistance (without|with no) hassle",
            r"my life changed after",
            r"i bought (my|a|the) [^\n]+ for my (son|daughter|family|wife|husband)",
            r"(contact|dm|message) @[a-zA-Z0-9_]{4,} (for|to get|for help|for more)",
            r"\$\d{2,5} (profit|returns|income|gain|withdrawal)",
            r"\d+% (daily|weekly|monthly) (returns?|profit|roi)",
            r"roi of \d+%",
        ]
        for pattern in scam_regexes:
            if re.search(pattern, message_lower):
                result['instant_ban'] = True
                result['reasons'].append(f"Regex scam pattern: {pattern}")
                result['triggers'].append("regex_scam")
                return result
        return result
    """Detects spam messages using multiple techniques"""
    
    def __init__(self):
        self.config = Config()
        
        # Whitelist of safe bot usernames (our own bot and known safe bots)
        self.safe_bot_usernames = [
            'mudrex_nightwatchman_bot',
            'nightwatchman_bot',
            # Add other safe bots as needed
        ]
        
        # Initialize ML classifier
        self.ml_classifier = None
        if ML_ENABLED:
            try:
                data_dir = getattr(self.config, 'ANALYTICS_DATA_DIR', 'data')
                self.ml_classifier = get_classifier(data_dir)
                logger.info("🤖 ML spam classifier initialized")
            except Exception as e:
                logger.error(f"Failed to initialize ML classifier: {e}")
        
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
        
        # Emoji pattern for counting (comprehensive - includes all common emoji ranges)
        self.emoji_pattern = re.compile(
            r'[\U0001F300-\U0001F9FF]|'  # Misc symbols, emoticons, etc.
            r'[\U00002600-\U000027BF]|'  # Misc symbols  
            r'[\U0001F100-\U0001F1FF]|'  # Enclosed characters
            r'[\u2600-\u26FF]|'          # Misc symbols
            r'[\u2700-\u27BF]|'          # Dingbats
            r'[\u2B50-\u2B55]|'          # Stars and circles (⭐ etc.)
            r'[\u2934-\u2935]|'          # Arrows
            r'[\u3030\u303D]|'           # Wavy dash, part alternation mark
            r'[\uFE0F]|'                 # Variation selector
            r'[\U0001F600-\U0001F64F]|'  # Emoticons
            r'[\U0001F680-\U0001F6FF]|'  # Transport & map symbols
            r'[\U0001F1E0-\U0001F1FF]'   # Flags
        )
    
    def analyze(self, message: str, user_id: int, user_join_date: Optional[datetime] = None,
                entities: Optional[List] = None, user_rep: int = 0, 
                is_first_message: bool = False) -> Dict:
        """
        Analyze a message for spam indicators
        
        Args:
            message: The message text
            user_id: Telegram user ID
            user_join_date: When user joined the group (for new user detection)
            entities: Telegram message entities (for detecting hyperlinks, etc.)
            user_rep: User's reputation points (0 = new/untrusted)
            is_first_message: True if this is user's first message in group
        
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
        instant_ban_result = self._check_instant_ban(message, message_lower, message_normalized, entities)
        if instant_ban_result['instant_ban']:
            result['is_spam'] = True
            result['instant_ban'] = True
            result['spam_score'] = 1.0
            result['action'] = 'delete_and_ban'
            result['reasons'] = instant_ban_result['reasons']
            result['details']['instant_ban_triggers'] = instant_ban_result['triggers']
            return result  # No further analysis needed
        
        # 0.5 MONEY EMOJI CHECK - Flag new/low-rep users using money emojis
        if self.config.MONEY_EMOJI_CHECK_ENABLED:
            money_result = self._check_money_emojis(message, user_id, user_join_date, user_rep, is_first_message)
            if money_result['is_spam']:
                result['is_spam'] = True
                result['spam_score'] = 0.8
                result['action'] = self.config.MONEY_EMOJI_ACTION
                result['reasons'] = money_result['reasons']
                result['details']['money_emoji_spam'] = True
                return result
        
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
            
            # Non-whitelisted links = immediate action if high score
            # Specifically check for instagram links or other social links often used for spam
            if any(u for u in url_details['suspicious']):
                 # Immediate mute for suspicious/non-whitelisted links
                 result['action'] = 'mute_24h' # Custom action for handler
                 result['is_spam'] = True
                 result['spam_score'] = 1.0 

        # 3. New user posting links
        if user_join_date:
            new_user_score = self._check_new_user(user_id, user_join_date, message)
            if new_user_score > 0:
                # If they say simple greetings, don't penalize as heavily unless back-to-back
                if len(message.split()) < 5 and not self.url_pattern.search(message):
                     # Short message, likely greeting. Reduce score
                     new_user_score = 0.1 
                
                result['spam_score'] += new_user_score
                if new_user_score > 0.3:
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
        
        # 11. ML-based spam detection (adaptive learning)
        if self.ml_classifier and self.ml_classifier.is_trained:
            ml_is_spam, ml_confidence = self.ml_classifier.predict(message)
            if ml_is_spam and ml_confidence >= 0.75:
                # High confidence ML detection
                result['spam_score'] += 0.4
                result['reasons'].append(f"ML classifier: {ml_confidence:.0%} spam confidence")
                result['details']['ml_confidence'] = ml_confidence
            elif ml_is_spam and ml_confidence >= 0.6:
                # Medium confidence - add smaller score
                result['spam_score'] += 0.2
                result['reasons'].append(f"ML classifier: {ml_confidence:.0%} spam confidence")
                result['details']['ml_confidence'] = ml_confidence
        
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
    
    def _check_instant_ban(self, message: str, message_lower: str, message_normalized: str,
                           entities: Optional[List] = None) -> Dict:
        """
        Check for patterns that warrant INSTANT BAN (no warnings).
        These are non-negotiable violations.
        
        Args:
            message: Original message text
            message_lower: Lowercase message
            message_normalized: Normalized message (special chars removed)
            entities: Telegram message entities (for detecting hyperlinks)
        """
        result = {'instant_ban': False, 'reasons': [], 'triggers': []}
        
        # FIRST: Check whitelist - legitimate questions should NEVER trigger ban
        if hasattr(self.config, 'WHITELISTED_PHRASES'):
            for phrase in self.config.WHITELISTED_PHRASES:
                if phrase.lower() in message_lower:
                    # This is a legitimate question, skip ALL instant ban checks
                    return result
        
        # Normalize text to detect Cyrillic obfuscation (х→x, р→p, о→o, etc.)
        message_deobfuscated = self._normalize_text(message)
        message_deobfuscated_lower = message_deobfuscated.lower()
        
        # 0. PREMIUM/CUSTOM EMOJI CHECK
        # Spammers use premium accounts to send custom emojis that bypass text detection
        if entities and getattr(self.config, 'PREMIUM_EMOJI_SPAM_ENABLED', True):
            custom_emoji_count = sum(
                1 for entity in entities 
                if entity.get('type') == 'custom_emoji'
            )
            threshold = getattr(self.config, 'PREMIUM_EMOJI_THRESHOLD', 5)
            if custom_emoji_count >= threshold:
                result['instant_ban'] = True
                result['reasons'].append(f"Premium emoji spam ({custom_emoji_count} custom emojis)")
                result['triggers'].append("premium_emoji_spam")
                return result
        
        # 1. HYPERLINK + EMOJI CHECK (text_link entities with 2+ emojis = instant ban)
        # This catches hidden links disguised with pretty emoji-laden text
        if entities:
            has_hyperlink = any(
                entity.get('type') in ['text_link', 'url'] 
                for entity in entities
            )
            if has_hyperlink:
                # Count emojis in message
                emoji_matches = self.emoji_pattern.findall(message)
                emoji_count = len(emoji_matches)
                if emoji_count > 2:
                    result['instant_ban'] = True
                    result['reasons'].append(f"Hyperlinked text with emojis ({emoji_count} emojis)")
                    result['triggers'].append("hyperlink_emoji_spam")
                    return result
        
        # 1. Adult/Porn content (obfuscated or not)
        # Check both original and deobfuscated versions
        if self.adult_patterns.search(message) or self.adult_patterns.search(message_deobfuscated):
            result['instant_ban'] = True
            result['reasons'].append("Adult/porn content detected")
            result['triggers'].append("adult_content")
            return result
        
        # 2. Telegram bot links (scam bots) - but not our own bot or safe bots
        bot_match = self.telegram_bot_pattern.search(message)
        if bot_match:
            matched_text = bot_match.group(0).lower()
            # Check if it's a safe/whitelisted bot
            is_safe_bot = False
            for safe_bot in self.safe_bot_usernames:
                if safe_bot in matched_text:
                    is_safe_bot = True
                    break
            
            # Also skip if it's a command format like /warn@botname
            if message.strip().startswith('/'):
                is_safe_bot = True  # Commands mentioning bots are not spam
            
            if not is_safe_bot:
                result['instant_ban'] = True
                result['reasons'].append("Telegram bot link detected")
                result['triggers'].append("telegram_bot_link")
                return result
        
        # 3. Casino/Betting spam - CONTEXTUAL detection
        # Definite casino spam (instant ban on these alone)
        definite_casino = [
            '1win', '1xbet', 'xwin', '22bet', 'melbet', 'mostbet', 'linebet',
            'casino bonus', 'free spins', 'slot machine', 'betting bonus',
            'on your balance', 'activate the promo', 'activate promo',
            'play anywhere', 'get $', 'your balance', 'promocasbot',
            'bet220', 'bet200', 'bet100', '$220', '$200 free', '$100 free'
        ]
        for keyword in definite_casino:
            if keyword in message_lower or keyword in message_deobfuscated_lower:
                result['instant_ban'] = True
                result['reasons'].append(f"Casino/betting spam detected: {keyword}")
                result['triggers'].append("casino_spam")
                return result
        
        # Contextual casino detection: "promo code" only banned if combined with spam signals
        # (This prevents false positives like "how to get promo codes in mudrex")
        has_promo_code = 'promo code' in message_lower or 'promo code' in message_deobfuscated_lower
        if has_promo_code:
            spam_signals = [
                'jackpot', 'casino', 'betting', 'win', 'bonus', 'free', 
                'balance', 'activate', '$', 'play', '🎰', '💰', '🎲'
            ]
            # Check for bot links or telegram links
            has_bot_link = '@' in message and ('bot' in message_lower or 'win' in message_lower)
            has_spam_signal = any(sig in message_lower for sig in spam_signals)
            has_many_emojis = len(self.emoji_pattern.findall(message)) >= 3
            
            if has_bot_link or (has_spam_signal and has_many_emojis):
                result['instant_ban'] = True
                result['reasons'].append("Promotional spam detected: promo code + spam signals")
                result['triggers'].append("contextual_casino_spam")
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
                keyword_lower = keyword.lower()
                # Check original, normalized, AND deobfuscated versions
                if keyword_lower in message_lower or keyword_lower in message_normalized or keyword_lower in message_deobfuscated_lower:
                    result['instant_ban'] = True
                    result['reasons'].append(f"Instant ban keyword: {keyword}")
                    result['triggers'].append("instant_ban_keyword")
                    return result
        
        # 6. Excessive emoji spam detection (promotional style)
        emoji_count = len(re.findall(r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001F100-\U0001F1FF]', message))
        special_chars = len(re.findall(r'[▫▪🔠🅰➡⬅✔💪⚡😆🍬💙🤍❤💜💋😈👩🔥✅❌⭐🎰🎲💰💵💎🏆🥇]', message))
        total_decorative = emoji_count + special_chars
        has_links = bool(self.url_pattern.search(message))
        
        # Promo-style messages: lots of emojis + links = instant ban
        if total_decorative > 8 and has_links:
            result['instant_ban'] = True
            result['reasons'].append("Promotional spam (excessive emojis + links)")
            result['triggers'].append("promo_spam")
            return result
        
        # Even without links, excessive promotional patterns get banned
        if total_decorative > 15:
            promo_keywords = ['right here', 'click', 'join', 'bonus', 'win', 'free', 
                             'ready', 'launch', 'promo', 'code', 'new players', 'get a',
                             'start', 'cash', 'today', 'now', 'hot', 'big']
            promo_matches = sum(1 for kw in promo_keywords if kw in message_lower)
            if promo_matches >= 2:
                result['instant_ban'] = True
                result['reasons'].append("Promotional spam (emoji overload + promo keywords)")
                result['triggers'].append("emoji_promo_spam")
                return result
        
        # 7. RECRUITMENT SCAM DETECTION
        # These scams promise remote work with unrealistic earnings + ask to DM
        recruitment_result = self._check_recruitment_scam(message, message_lower, message_normalized)
        if recruitment_result['instant_ban']:
            return recruitment_result

        # 8. FLEXIBLE SCAM PATTERN DETECTION (regex/partial phrase)
        flexible_scam_result = self._check_flexible_scam_patterns(message, message_lower)
        if flexible_scam_result['instant_ban']:
            return flexible_scam_result
        
        return result
    
    def _check_recruitment_scam(self, message: str, message_lower: str, message_normalized: str) -> Dict:
        """
        Detect recruitment/job scam patterns.
        These scams promise remote work with unrealistic earnings and ask victims to DM.
        
        Pattern: earnings claim + remote work + DM request + telegram handle
        """
        result = {'instant_ban': False, 'reasons': [], 'triggers': []}
        
        # Check for @ mentions (DM targets)
        has_telegram_handle = bool(re.search(r'@[a-zA-Z][a-zA-Z0-9_]{4,}', message))
        
        # Earnings patterns with dollar amounts (including spelled out "dollars")
        earnings_patterns = [
            r'\$\d{2,4}\s*(per|a)\s*(day|week)',  # $120 per day, $1050 per week
            r'\$\d{2,4}\s*-\s*\$\d{2,4}',  # $120-$250
            r'(earnings?|income|earn)\s*(from|starting|of|up to)?\s*\$\d+',  # earnings from $120
            r'\$\d+\+?\s*(per|a|/)\s*(day|week)',  # $1,000+ per week
            r'(up to|starting at)\s*\$\d+',  # up to $1050
            r'\d{2,4}\s*(dollars?|usd)\s*(per|a)\s*(day|week)',  # 70-80 dollars per day
            r'\d{2,4}\s*-\s*\d{2,4}\s*(dollars?|usd)',  # 70-80 dollars
            r'\$\d+\s*[–-]\s*\$\d+',  # $500–$1,000 (en-dash or hyphen)
        ]
        has_earnings_claim = any(re.search(p, message_lower) for p in earnings_patterns)
        
        # Remote work keywords
        remote_keywords = [
            'remote', 'remotely', 'from home', 'from a phone', 'from phone',
            'from a computer', 'from computer', 'work online', 'online work',
            'completely remote', 'fully remote', 'remote employment', 
            'remote job', 'online project', 'via phone', 'via pc',
            'only via phone', 'phone or pc'
        ]
        has_remote_keyword = any(kw in message_lower for kw in remote_keywords)
        
        # Recruitment language
        recruitment_keywords = [
            'looking for', 'recruiting', 'recruitment', 'opening recruitment',
            'join a project', 'join my team', 'putting together', 'team',
            'looking for people', 'looking for partners', 'looking for several',
            '2-3 people', 'two people', 'several people', 'responsible people',
            '2-3 individuals', 'seeking', 'urgently seeking', 'new online project',
            'cool project', 'join my team at', 'activities on bybit',
            'activities on binance', 'we\'re recruiting'
        ]
        has_recruitment = any(kw in message_lower for kw in recruitment_keywords)
        
        # DM request patterns
        dm_patterns = [
            'write to', 'message me', 'dm me', 'private message',
            'send me a', 'contact me', 'write "+"', "write '+'", 'leave a "+"',
            'write +', 'leave +', 'interested, message', 'if interested',
            'details:', 'details -', 'want to join', 'details in pm',
            'details in dm', 'write now', 'write to me at', 'send me a private',
            'pm -', 'dm -', 'pm:', 'write me'
        ]
        has_dm_request = any(kw in message_lower for kw in dm_patterns)
        
        # Easy work promises
        easy_work_patterns = [
            'simple tasks', 'clear instructions', 'easy', '1-2 hours',
            '1.5-2 hours', 'hours per day', 'full training', 'training and support',
            'we provide', 'daily payments', 'transparent'
        ]
        has_easy_promise = any(kw in message_lower for kw in easy_work_patterns)
        
        # Attention grabbers (suspicious)
        attention_patterns = [
            'attention', '‼️', '❗', '⚡', '❗️', '✔', '✅'
        ]
        has_attention = any(kw in message for kw in attention_patterns)
        
        # Check for "legal" claims (often used by scammers to add legitimacy)
        legal_keywords = ['legal', 'secure', 'legitimate', 'legit', 'safe', 'trusted']
        has_legal_claim = any(kw in message_lower for kw in legal_keywords)
        
        # SCORING: Need combination of signals to trigger
        score = 0
        triggers = []
        
        if has_telegram_handle:
            score += 1.5  # Increased - key scam indicator
            triggers.append("telegram_handle")
        if has_earnings_claim:
            score += 2  # Strong signal
            triggers.append("earnings_claim")
        if has_remote_keyword:
            score += 1
            triggers.append("remote_work")
        if has_recruitment:
            score += 1.5  # Increased
            triggers.append("recruitment_language")
        if has_dm_request:
            score += 2  # Strong signal
            triggers.append("dm_request")
        if has_easy_promise:
            score += 1
            triggers.append("easy_money_promise")
        if has_attention:
            score += 1  # Increased from 0.5
            triggers.append("attention_grabber")
        if has_legal_claim:
            score += 0.5  # "Legal" claims are suspicious in this context
            triggers.append("legal_claim")
        
        # Bonus: telegram handle + attention emojis + recruitment = very suspicious
        if has_telegram_handle and has_attention and has_recruitment:
            score += 1
            triggers.append("combo_bonus")
        
        # Instant ban if score >= 3.5 (lowered from 4 to catch more scams)
        if score >= 3.5:
            result['instant_ban'] = True
            result['reasons'].append(f"Recruitment scam detected (score: {score})")
            result['triggers'] = triggers
        
        return result

    def _check_money_emojis(self, message: str, user_id: int, 
                            user_join_date: Optional[datetime], 
                            user_rep: int, is_first_message: bool) -> Dict:
        """
        Check for money/dollar emojis from new or low-reputation users.
        These emojis are commonly used in scam/promo messages.
        
        Args:
            message: The message text
            user_id: Telegram user ID
            user_join_date: When user joined the group
            user_rep: User's reputation points
            is_first_message: True if this is user's first message
        
        Returns:
            Dict with is_spam flag and reasons
        """
        result = {'is_spam': False, 'reasons': []}
        
        # Count money emojis in message
        money_emojis = getattr(self.config, 'MONEY_EMOJIS', 
                               ['💰', '💵', '💸', '🤑', '💲', '💳', '🏧', '💎', '🪙'])
        money_emoji_count = sum(1 for char in message if char in money_emojis)
        
        threshold = getattr(self.config, 'MONEY_EMOJI_THRESHOLD', 2)
        
        if money_emoji_count < threshold:
            return result  # Not enough money emojis
        
        # Check if user is "suspicious" (new, low rep, or first message)
        is_suspicious = False
        suspicion_reasons = []
        
        # Check 1: First message ever
        if is_first_message:
            is_suspicious = True
            suspicion_reasons.append("first message")
        
        # Check 2: Low reputation (0 or below minimum)
        min_rep = getattr(self.config, 'MONEY_EMOJI_MIN_REP', 1)
        if user_rep < min_rep:
            is_suspicious = True
            suspicion_reasons.append(f"low reputation ({user_rep})")
        
        # Check 3: New user (joined within threshold hours)
        if user_join_date:
            now = datetime.now(timezone.utc)
            # Ensure join_date is timezone-aware
            if user_join_date.tzinfo is None:
                user_join_date = user_join_date.replace(tzinfo=timezone.utc)
            
            hours_since_join = (now - user_join_date).total_seconds() / 3600
            threshold_hours = getattr(self.config, 'MONEY_EMOJI_NEW_USER_HOURS', 48)
            
            if hours_since_join < threshold_hours:
                is_suspicious = True
                suspicion_reasons.append(f"new user ({int(hours_since_join)}h old)")
        
        if is_suspicious:
            result['is_spam'] = True
            emojis_found = [char for char in message if char in money_emojis][:5]  # Show first 5
            result['reasons'].append(
                f"Money emoji spam ({money_emoji_count}x {''.join(emojis_found)}) from {', '.join(suspicion_reasons)}"
            )
        
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
            # Instagram is not implicitly suspicious but is not whitelisted, so we trap it
            if "instagram.com" in url_lower or "youtu.be" in url_lower or "youtube.com" in url_lower:
                # Treat as suspicious because it's non-whitelisted external link
                is_suspicious = True
                
            if is_suspicious:
                details['suspicious'].append(url)
                score += 0.8 # High score for known suspicious/unwanted links
            else:
                # Unknown external link
                details['suspicious'].append(url) # Treat all unknown as suspicious for now per request
                score += 0.8
        
        return min(score, 1.0), details
    
    def _check_new_user(self, user_id: int, join_date: datetime, message: str) -> float:
        """Check if new user is posting links"""
        now = datetime.now(timezone.utc)
        hours_in_group = (now - join_date).total_seconds() / 3600
        
        if hours_in_group < self.config.NEW_USER_LINK_BLOCK_HOURS:
            # New user - check if they're posting links
            if self.url_pattern.search(message):
                return 0.6
        return 0.0
    
    # Security: Maximum users to track in memory (prevents memory exhaustion)
    MAX_TRACKED_USERS = 10000
    
    def _check_rate_limit(self, user_id: int) -> float:
        """Check if user is sending too many messages"""
        now = datetime.now(timezone.utc)
        one_minute_ago = now - timedelta(minutes=1)
        
        # Security: Prune stale users to prevent memory exhaustion
        if len(self.user_messages) > self.MAX_TRACKED_USERS:
            # Remove users with oldest activity
            stale_users = []
            for uid, timestamps in self.user_messages.items():
                if not timestamps or all(t < one_minute_ago for t in timestamps):
                    stale_users.append(uid)
            for uid in stale_users[:len(stale_users)//2]:  # Remove half of stale users
                del self.user_messages[uid]
            logger.info(f"🛡️ Pruned {len(stale_users[:len(stale_users)//2])} stale users from rate-limit tracker")
        
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
    
    def learn_spam(self, message: str):
        """
        Add a message to the ML spam training set.
        Called when an admin bans a user for spam.
        """
        if self.ml_classifier:
            self.ml_classifier.add_spam_sample(message)
    
    def learn_ham(self, message: str):
        """
        Add a message to the ML ham (non-spam) training set.
        Called when a message is falsely flagged.
        """
        if self.ml_classifier:
            self.ml_classifier.add_ham_sample(message)
    
    def get_ml_stats(self) -> Dict:
        """Get ML classifier statistics."""
        if self.ml_classifier:
            return self.ml_classifier.get_stats()
        return {"ml_available": False, "is_trained": False}