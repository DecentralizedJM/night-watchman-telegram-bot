"""
Night Watchman - User Behavior Profiler
Tracks user behavior patterns, builds profiles, and detects anomalies
"""

import json
import logging
import os
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from statistics import mean, stdev

logger = logging.getLogger(__name__)


class BehaviorProfiler:
    """
    Tracks user behavior patterns and detects anomalies.
    
    Features:
    - Message timing patterns (active hours, frequency)
    - Content patterns (message length, emoji usage, link frequency)
    - Activity patterns (messages per day, join patterns)
    - Anomaly detection (sudden behavior changes)
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.profiles_path = os.path.join(data_dir, "user_profiles.json")
        
        # In-memory tracking (for real-time analysis)
        self.user_message_times: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))
        self.user_message_lengths: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))
        self.user_link_counts: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))
        self.user_emoji_counts: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))
        self.user_activity_days: Dict[int, set] = defaultdict(set)
        
        # Daily activity tracking
        self.daily_message_counts: Dict[int, Dict[str, int]] = defaultdict(dict)  # user_id -> {date: count}
        
        # Load saved profiles
        self.profiles = self._load_profiles()
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
    
    def _load_profiles(self) -> Dict:
        """Load user behavior profiles from disk"""
        if os.path.exists(self.profiles_path):
            try:
                with open(self.profiles_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading user profiles: {e}")
        return {}
    
    def _save_profiles(self):
        """Save user behavior profiles to disk"""
        try:
            # Keep only profiles for active users (seen in last 90 days)
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
            active_profiles = {
                user_id: profile for user_id, profile in self.profiles.items()
                if profile.get('last_seen', '') > cutoff_date
            }
            
            with open(self.profiles_path, 'w', encoding='utf-8') as f:
                json.dump(active_profiles, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving user profiles: {e}")
    
    def track_message(self, user_id: int, message_text: str, timestamp: Optional[datetime] = None):
        """
        Track a user's message for behavior analysis.
        
        Args:
            user_id: Telegram user ID
            message_text: Message content
            timestamp: Message timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        # Track message timing
        hour = timestamp.hour
        self.user_message_times[user_id].append(hour)
        
        # Track message characteristics
        msg_len = len(message_text)
        self.user_message_lengths[user_id].append(msg_len)
        
        # Count links
        link_count = message_text.count('http://') + message_text.count('https://') + message_text.count('t.me/')
        self.user_link_counts[user_id].append(link_count)
        
        # Count emojis (simple approximation)
        emoji_count = sum(1 for char in message_text if ord(char) > 127 and char not in message_text.encode('ascii', 'ignore').decode('ascii'))
        self.user_emoji_counts[user_id].append(emoji_count)
        
        # Track activity days
        date_str = timestamp.date().isoformat()
        self.user_activity_days[user_id].add(date_str)
        self.daily_message_counts[user_id][date_str] = self.daily_message_counts[user_id].get(date_str, 0) + 1
    
    def get_user_profile(self, user_id: int) -> Dict:
        """
        Get or create a user behavior profile.
        
        Returns:
            Dict with behavior statistics
        """
        if user_id not in self.profiles:
            self.profiles[user_id] = {
                'created_at': datetime.now(timezone.utc).isoformat(),
                'last_seen': datetime.now(timezone.utc).isoformat(),
                'message_count': 0,
                'active_hours': [],
                'avg_message_length': 0,
                'avg_link_count': 0,
                'avg_emoji_count': 0,
                'active_days': 0,
                'messages_per_day': 0,
            }
        
        profile = self.profiles[user_id]
        profile['last_seen'] = datetime.now(timezone.utc).isoformat()
        
        # Update statistics from in-memory data
        if self.user_message_times[user_id]:
            profile['active_hours'] = list(set(self.user_message_times[user_id]))
            profile['message_count'] = len(self.user_message_times[user_id])
            
            if self.user_message_lengths[user_id]:
                profile['avg_message_length'] = mean(self.user_message_lengths[user_id])
            if self.user_link_counts[user_id]:
                profile['avg_link_count'] = mean(self.user_link_counts[user_id])
            if self.user_emoji_counts[user_id]:
                profile['avg_emoji_count'] = mean(self.user_emoji_counts[user_id])
            
            profile['active_days'] = len(self.user_activity_days[user_id])
            if profile['active_days'] > 0:
                total_messages = sum(self.daily_message_counts[user_id].values())
                profile['messages_per_day'] = total_messages / profile['active_days']
        
        return profile
    
    def detect_anomaly(self, user_id: int, message_text: str, timestamp: Optional[datetime] = None) -> Tuple[bool, float, List[str]]:
        """
        Detect if a user's current message is anomalous compared to their profile.
        
        Args:
            user_id: Telegram user ID
            message_text: Current message content
            timestamp: Message timestamp
            
        Returns:
            Tuple of (is_anomaly, anomaly_score, reasons)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        profile = self.get_user_profile(user_id)
        reasons = []
        anomaly_score = 0.0
        
        # Need at least some history to detect anomalies
        if profile['message_count'] < 5:
            return False, 0.0, []
        
        # Check message length anomaly
        current_len = len(message_text)
        avg_len = profile.get('avg_message_length', 0)
        if avg_len > 0:
            len_ratio = current_len / avg_len
            if len_ratio > 3.0 or len_ratio < 0.2:  # 3x longer or 5x shorter
                anomaly_score += 0.3
                reasons.append(f"Unusual message length ({len_ratio:.1f}x normal)")
        
        # Check link count anomaly
        current_links = message_text.count('http://') + message_text.count('https://') + message_text.count('t.me/')
        avg_links = profile.get('avg_link_count', 0)
        if avg_links < 0.1 and current_links > 0:  # User rarely posts links, but this message has links
            anomaly_score += 0.4
            reasons.append(f"User rarely posts links, but message contains {current_links} links")
        elif avg_links > 0 and current_links > avg_links * 2:
            anomaly_score += 0.3
            reasons.append(f"Unusual link count ({current_links} vs avg {avg_links:.1f})")
        
        # Check emoji count anomaly
        current_emojis = sum(1 for char in message_text if ord(char) > 127)
        avg_emojis = profile.get('avg_emoji_count', 0)
        if avg_emojis < 1 and current_emojis > 5:  # User rarely uses emojis, but this message has many
            anomaly_score += 0.2
            reasons.append(f"Unusual emoji usage ({current_emojis} emojis vs avg {avg_emojis:.1f})")
        
        # Check activity hour anomaly
        current_hour = timestamp.hour
        active_hours = profile.get('active_hours', [])
        if active_hours and current_hour not in active_hours:
            # Check if it's very different (e.g., user usually active 9-17, but posting at 3 AM)
            if active_hours:
                typical_start = min(active_hours)
                typical_end = max(active_hours)
                if current_hour < typical_start - 3 or current_hour > typical_end + 3:
                    anomaly_score += 0.2
                    reasons.append(f"Unusual posting time ({current_hour}:00 vs typical {typical_start}:00-{typical_end}:00)")
        
        # Check message frequency anomaly (too many messages in short time)
        recent_times = list(self.user_message_times[user_id])[-10:]
        if len(recent_times) >= 5:
            # User is posting much faster than usual
            avg_messages_per_day = profile.get('messages_per_day', 1)
            if avg_messages_per_day > 0:
                # If user typically posts 5 messages/day, but posted 5 in last hour = anomaly
                time_span_hours = 1  # Last hour
                messages_in_period = len([t for t in recent_times if t == timestamp.hour])
                expected_in_period = (avg_messages_per_day / 24) * time_span_hours
                if expected_in_period > 0 and messages_in_period > expected_in_period * 5:
                    anomaly_score += 0.3
                    reasons.append(f"Unusual message frequency ({messages_in_period} messages in short period)")
        
        is_anomaly = anomaly_score >= 0.5  # Threshold for anomaly
        return is_anomaly, anomaly_score, reasons
    
    def save(self):
        """Save profiles to disk"""
        self._save_profiles()
    
    def get_stats(self) -> Dict:
        """Get profiler statistics"""
        return {
            'profiled_users': len(self.profiles),
            'active_users': len([p for p in self.profiles.values() 
                               if (datetime.now(timezone.utc) - datetime.fromisoformat(p.get('last_seen', '2000-01-01'))).days < 30])
        }
