"""
Night Watchman - Adaptive Threshold System
Learns optimal spam detection thresholds per group
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class AdaptiveThresholds:
    """
    Learns optimal spam detection thresholds per group.
    
    Features:
    - Per-group threshold learning
    - Adjusts thresholds based on false positives/negatives
    - Tracks group-specific patterns
    - Prevents over-adjustment
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.thresholds_path = os.path.join(data_dir, "adaptive_thresholds.json")
        
        # Default thresholds
        self.default_thresholds = {
            'delete_and_warn': 0.7,
            'delete_only': 0.5,
            'flag_for_review': 0.3
        }
        
        # Per-group thresholds
        self.group_thresholds: Dict[int, Dict] = self._load_thresholds()
        
        # Track false positives/negatives per group
        self.false_positives: Dict[int, int] = defaultdict(int)  # chat_id -> count
        self.false_negatives: Dict[int, int] = defaultdict(int)  # chat_id -> count
        self.total_decisions: Dict[int, int] = defaultdict(int)  # chat_id -> count
        
        # Track admin actions (warns/bans) as ground truth
        self.admin_actions: Dict[int, list] = defaultdict(list)  # chat_id -> list of (score, action_type)
        
        os.makedirs(data_dir, exist_ok=True)
    
    def _load_thresholds(self) -> Dict:
        """Load group thresholds from disk"""
        if os.path.exists(self.thresholds_path):
            try:
                with open(self.thresholds_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Convert string keys (from JSON) to int
                    return {int(k): v for k, v in data.items()}
            except Exception as e:
                logger.error(f"Error loading adaptive thresholds: {e}")
        return {}
    
    def _save_thresholds(self):
        """Save group thresholds to disk"""
        try:
            with open(self.thresholds_path, 'w', encoding='utf-8') as f:
                json.dump(self.group_thresholds, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving adaptive thresholds: {e}")
    
    def get_thresholds(self, chat_id: int) -> Dict[str, float]:
        """
        Get thresholds for a group (use learned or default).
        
        Args:
            chat_id: Chat ID
            
        Returns:
            Dict with threshold values
        """
        if chat_id in self.group_thresholds:
            return self.group_thresholds[chat_id]
        return self.default_thresholds.copy()
    
    def record_decision(self, chat_id: int, spam_score: float, action_taken: str):
        """
        Record a moderation decision for learning.
        
        Args:
            chat_id: Chat ID
            spam_score: Spam score of the message
            action_taken: Action taken ('delete_and_warn', 'delete_only', 'flag', 'none')
        """
        self.total_decisions[chat_id] += 1
        
        # Get current thresholds
        thresholds = self.get_thresholds(chat_id)
        
        # Determine expected action based on score
        expected_action = 'none'
        if spam_score >= thresholds['delete_and_warn']:
            expected_action = 'delete_and_warn'
        elif spam_score >= thresholds['delete_only']:
            expected_action = 'delete_only'
        elif spam_score >= thresholds['flag_for_review']:
            expected_action = 'flag'
        
        # Track if decision was correct (for future learning)
        # This will be updated when admin takes action
        if chat_id not in self.admin_actions:
            self.admin_actions[chat_id] = []
    
    def record_admin_action(self, chat_id: int, spam_score: float, admin_action: str):
        """
        Record an admin action (warn/ban/unwarn) as ground truth.
        
        Args:
            chat_id: Chat ID
            spam_score: Original spam score
            admin_action: Admin action ('warn', 'ban', 'unwarn')
        """
        if chat_id not in self.admin_actions:
            self.admin_actions[chat_id] = []
        
        self.admin_actions[chat_id].append({
            'score': spam_score,
            'action': admin_action,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        # Keep only recent actions (last 100)
        if len(self.admin_actions[chat_id]) > 100:
            self.admin_actions[chat_id] = self.admin_actions[chat_id][-100:]
    
    def record_false_positive(self, chat_id: int):
        """Record a false positive (message flagged but admin unwarned/unbanned)"""
        self.false_positives[chat_id] += 1
        self._adjust_thresholds_up(chat_id)  # Increase threshold (be less aggressive)
    
    def record_false_negative(self, chat_id: int):
        """Record a false negative (message not flagged but admin warned/banned)"""
        self.false_negatives[chat_id] += 1
        self._adjust_thresholds_down(chat_id)  # Decrease threshold (be more aggressive)
    
    def _adjust_thresholds_up(self, chat_id: int):
        """Increase thresholds (be less aggressive)"""
        thresholds = self.get_thresholds(chat_id)
        
        # Small adjustments (0.05 increments)
        adjustment = 0.05
        
        if chat_id not in self.group_thresholds:
            self.group_thresholds[chat_id] = thresholds.copy()
        
        # Adjust thresholds upward
        self.group_thresholds[chat_id]['delete_and_warn'] = min(0.95, thresholds['delete_and_warn'] + adjustment)
        self.group_thresholds[chat_id]['delete_only'] = min(0.85, thresholds['delete_only'] + adjustment)
        self.group_thresholds[chat_id]['flag_for_review'] = min(0.5, thresholds['flag_for_review'] + adjustment)
        
        logger.info(f"📊 Adjusted thresholds UP for chat {chat_id} (less aggressive)")
        self._save_thresholds()
    
    def _adjust_thresholds_down(self, chat_id: int):
        """Decrease thresholds (be more aggressive)"""
        thresholds = self.get_thresholds(chat_id)
        
        # Small adjustments (0.05 increments)
        adjustment = 0.05
        
        if chat_id not in self.group_thresholds:
            self.group_thresholds[chat_id] = thresholds.copy()
        
        # Adjust thresholds downward (but keep minimum bounds)
        self.group_thresholds[chat_id]['delete_and_warn'] = max(0.5, thresholds['delete_and_warn'] - adjustment)
        self.group_thresholds[chat_id]['delete_only'] = max(0.3, thresholds['delete_only'] - adjustment)
        self.group_thresholds[chat_id]['flag_for_review'] = max(0.1, thresholds['flag_for_review'] - adjustment)
        
        logger.info(f"📊 Adjusted thresholds DOWN for chat {chat_id} (more aggressive)")
        self._save_thresholds()
    
    def learn_from_admin_actions(self, chat_id: int):
        """
        Learn optimal thresholds from admin actions.
        Called periodically to analyze admin corrections.
        """
        if chat_id not in self.admin_actions or len(self.admin_actions[chat_id]) < 10:
            return  # Need at least 10 admin actions to learn
        
        actions = self.admin_actions[chat_id]
        
        # Analyze patterns
        unwarn_scores = [a['score'] for a in actions if a['action'] == 'unwarn']
        warn_scores = [a['score'] for a in actions if a['action'] in ['warn', 'ban']]
        
        if unwarn_scores and warn_scores:
            # If admin unwarned messages with high scores, threshold was too low
            avg_unwarn_score = sum(unwarn_scores) / len(unwarn_scores)
            avg_warn_score = sum(warn_scores) / len(warn_scores)
            
            thresholds = self.get_thresholds(chat_id)
            
            # If unwarned messages had scores > threshold, adjust up
            if unwarn_scores and avg_unwarn_score > thresholds['delete_and_warn']:
                self._adjust_thresholds_up(chat_id)
            
            # If warned messages had scores < threshold, adjust down
            if warn_scores and avg_warn_score < thresholds['delete_and_warn']:
                self._adjust_thresholds_down(chat_id)
    
    def get_group_stats(self, chat_id: int) -> Dict:
        """Get statistics for a group"""
        thresholds = self.get_thresholds(chat_id)
        is_custom = chat_id in self.group_thresholds
        
        return {
            'thresholds': thresholds,
            'is_custom': is_custom,
            'false_positives': self.false_positives.get(chat_id, 0),
            'false_negatives': self.false_negatives.get(chat_id, 0),
            'total_decisions': self.total_decisions.get(chat_id, 0),
            'admin_actions': len(self.admin_actions.get(chat_id, []))
        }
    
    def save(self):
        """Save thresholds to disk"""
        self._save_thresholds()
