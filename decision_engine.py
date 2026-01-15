
import logging
import time
from collections import deque, defaultdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class DecisionEngine:
    """
    Decides whether to Ban, Warn, or do nothing based on user history context.
    Prevents banning regular users for single mistakes.
    """
    
    def __init__(self, history_size=10, max_users=5000):
        self.history_size = history_size
        self.max_users = max_users
        # user_id -> deque of message dicts {'text': str, 'score': float, 'ts': float}
        self.user_history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=history_size))
        self.last_access: Dict[int, float] = {}

    def track_message(self, user_id: int, text: str, spam_score: float = 0.0):
        """Track a new message from a user."""
        self._cleanup_if_needed()
        
        self.user_history[user_id].append({
            'text': text,
            'score': spam_score,
            'ts': time.time()
        })
        self.last_access[user_id] = time.time()

    def make_decision(self, user_id: int, proposed_action: str, violation_type: str = "generic") -> Tuple[str, str]:
        """
        Review the proposed action against user history.
        Returns: (final_action, reasoning)
        """
        if user_id not in self.user_history:
             # New user or no history - trust the proposed action
             return proposed_action, "No history"

        history = list(self.user_history[user_id])
        msg_count = len(history)
        
        # 1. ALWAYS BAN: Very Severe Violations
        very_severe = ['adult_content', 'telegram_bot_link', 'malware', 'bot_account']
        if violation_type in very_severe:
            return proposed_action, f"Severe violation ({violation_type}) overrides history"

        # 2. CHECK HISTORY (Only relevant for bans)
        if proposed_action in ['delete_and_ban', 'ban']:
            # Calculate "Safe" messages (low spam score)
            safe_messages = sum(1 for m in history if m['score'] < 0.4)
            safe_ratio = safe_messages / msg_count if msg_count > 0 else 0
            
            # Criteria for Mercy:
            # - At least 5 recent messages
            # - 80% of them were safe
            if msg_count >= 5 and safe_ratio >= 0.8:
                new_action = 'delete_and_warn'
                reason = f"decision_engine: Downgraded to WARN (Safe Ratio: {safe_ratio:.0%}, {msg_count} msgs)"
                logger.info(f"⚖️ Spared user {user_id} from ban. {reason}")
                return new_action, reason
        
        return proposed_action, "History does not warrant leniency"

    def _cleanup_if_needed(self):
        """Simple LRU cleanup if user limit reached."""
        if len(self.user_history) > self.max_users:
            # Remove 10% of users based on last access (LRU)
            sorted_users = sorted(self.last_access.items(), key=lambda x: x[1])
            to_remove = int(self.max_users * 0.1)
            for uid, _ in sorted_users[:to_remove]:
                del self.user_history[uid]
                del self.last_access[uid]
