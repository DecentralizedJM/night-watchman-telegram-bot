"""
Night Watchman - Context-Aware Moderation
Understands conversation context before taking moderation actions
"""

import logging
import re
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ContextAnalyzer:
    """
    Analyzes conversation context to make better moderation decisions.
    
    Features:
    - Conversation thread analysis
    - Topic detection
    - Legitimate discussion detection
    - Group-specific context learning
    """
    
    def __init__(self):
        # Store recent messages per chat for context
        self.recent_messages: Dict[int, deque] = {}  # chat_id -> deque of recent messages
        self.context_window = 20  # Keep last 20 messages for context
        self.context_window_minutes = 30  # Context window time limit
        
        # Legitimate discussion patterns (to avoid false positives)
        self.legitimate_patterns = [
            # Questions/discussions about crypto/trading
            r'how (to|do|can|does)',
            r'what (is|are|does|do)',
            r'why (is|are|does|do)',
            r'when (is|are|does|do|will)',
            r'can (you|i|we)',
            r'help (me|with)',
            r'explain',
            r'question',
            r'asking about',
            # Discussions
            r'i (think|believe|feel)',
            r'in my opinion',
            r'what do you think',
            r'discuss',
            # Information sharing (not spam)
            r'according to',
            r'based on',
            r'from what i (know|understand)',
        ]
    
    def add_message(self, chat_id: int, user_id: int, message_text: str, timestamp: Optional[datetime] = None):
        """
        Add a message to the context for a chat.
        
        Args:
            chat_id: Chat ID
            user_id: User ID
            message_text: Message text
            timestamp: Message timestamp
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        if chat_id not in self.recent_messages:
            self.recent_messages[chat_id] = deque(maxlen=self.context_window)
        
        self.recent_messages[chat_id].append({
            'user_id': user_id,
            'text': message_text,
            'timestamp': timestamp
        })
        
        # Clean old messages (outside time window)
        cutoff_time = timestamp - timedelta(minutes=self.context_window_minutes)
        while (self.recent_messages[chat_id] and 
               self.recent_messages[chat_id][0]['timestamp'] < cutoff_time):
            self.recent_messages[chat_id].popleft()
    
    def get_context(self, chat_id: int) -> List[Dict]:
        """Get recent message context for a chat"""
        return list(self.recent_messages.get(chat_id, []))
    
    def analyze_context(self, chat_id: int, current_message: str, current_user_id: int) -> Dict:
        """
        Analyze conversation context to determine if message is legitimate discussion.
        
        Args:
            chat_id: Chat ID
            current_message: Current message text
            current_user_id: Current user ID
            
        Returns:
            Dict with context analysis results
        """
        context = self.get_context(chat_id)
        current_lower = current_message.lower()
        
        result = {
            'is_legitimate_discussion': False,
            'is_continuation': False,
            'is_question': False,
            'context_score': 0.0,
            'reasons': []
        }
        
        if not context:
            return result
        
        # Check if current message is a question (likely legitimate)
        question_indicators = ['?', 'how', 'what', 'why', 'when', 'where', 'who', 'can', 'should', 'would']
        if any(indicator in current_lower for indicator in question_indicators):
            result['is_question'] = True
            result['context_score'] += 0.3
            result['reasons'].append("Message appears to be a question")
        
        # Check if message is part of an ongoing discussion
        # Look for references to previous messages (replies, mentions, topic continuation)
        if len(context) >= 2:
            # Check if user is replying to/continuing a discussion
            reply_indicators = ['yes', 'no', 'i agree', 'i disagree', 'also', 'but', 'however', 'actually', 'exactly', 'that\'s']
            if any(indicator in current_lower for indicator in reply_indicators):
                result['is_continuation'] = True
                result['context_score'] += 0.4
                result['reasons'].append("Message appears to continue a discussion")
            
            # Check if message references previous messages
            recent_texts = ' '.join([msg['text'].lower() for msg in context[-3:]])
            # Simple check: if current message shares words with recent messages, it's likely related
            current_words = set(current_lower.split())
            recent_words = set(recent_texts.split())
            common_words = current_words.intersection(recent_words)
            # Filter out common words
            common_words = {w for w in common_words if len(w) > 4}
            if len(common_words) >= 2:
                result['is_continuation'] = True
                result['context_score'] += 0.3
                result['reasons'].append(f"Message references recent discussion ({len(common_words)} common keywords)")
        
        # Check if message matches legitimate discussion patterns
        for pattern in self.legitimate_patterns:
            if re.search(pattern, current_lower):
                result['is_legitimate_discussion'] = True
                result['context_score'] += 0.5
                result['reasons'].append("Message matches legitimate discussion pattern")
                break
        
        # Check if user is participating in an active discussion
        # (not spamming in isolation)
        if len(context) >= 3:
            # Count unique users in recent context
            recent_users = set(msg['user_id'] for msg in context[-5:])
            if len(recent_users) >= 2 and current_user_id in recent_users:
                # User is part of an active multi-user conversation
                result['context_score'] += 0.2
                result['reasons'].append("User is part of active discussion")
        
        # Determine if legitimate based on score
        result['is_legitimate_discussion'] = result['context_score'] >= 0.5
        
        return result
    
    def should_reduce_spam_score(self, chat_id: int, message_text: str, user_id: int, spam_score: float) -> Tuple[float, List[str]]:
        """
        Analyze context and adjust spam score accordingly.
        
        Args:
            chat_id: Chat ID
            message_text: Message text
            user_id: User ID
            spam_score: Original spam score
            
        Returns:
            Tuple of (adjusted_score, reasons)
        """
        context_result = self.analyze_context(chat_id, message_text, user_id)
        
        adjusted_score = spam_score
        reasons = []
        
        # Reduce score if message is legitimate discussion
        if context_result['is_legitimate_discussion']:
            reduction = min(0.4, spam_score * 0.6)  # Reduce by 40% or 60% of current score
            adjusted_score = max(0.0, spam_score - reduction)
            reasons.extend(context_result['reasons'])
            reasons.append(f"Context analysis reduced spam score by {reduction:.2f}")
        
        return adjusted_score, reasons
    
    def cleanup_old_context(self):
        """Remove old context data (call periodically)"""
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(minutes=self.context_window_minutes * 2)
        
        for chat_id in list(self.recent_messages.keys()):
            # Remove old messages
            while (self.recent_messages[chat_id] and 
                   self.recent_messages[chat_id][0]['timestamp'] < cutoff_time):
                self.recent_messages[chat_id].popleft()
            
            # Remove empty contexts
            if not self.recent_messages[chat_id]:
                del self.recent_messages[chat_id]
