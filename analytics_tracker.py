"""
Night Watchman - Analytics Tracker
Tracks group statistics for admin reporting
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
from config import Config

logger = logging.getLogger(__name__)


class AnalyticsTracker:
    """
    Tracks group analytics for admin reporting.
    
    Metrics tracked:
    - Member joins/exits per day
    - Messages per day
    - Spam blocked per day
    - Users warned/muted/banned per day
    - Active users per day
    - Peak activity hours
    """
    
    def __init__(self):
        self.config = Config()
        self.data_dir = self.config.ANALYTICS_DATA_DIR
        self.data_file = os.path.join(self.data_dir, "analytics.json")
        self.data = self._load_data()
        self._ensure_structure()
    
    def _ensure_structure(self):
        """Ensure data has correct structure"""
        if 'daily' not in self.data:
            self.data['daily'] = {}
        if 'hourly' not in self.data:
            self.data['hourly'] = {}
    
    def _load_data(self) -> Dict:
        """Load analytics data from file"""
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading analytics data: {e}")
        return {}
    
    def _save_data(self):
        """Save analytics data to file"""
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            with open(self.data_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving analytics data: {e}")
    
    def _get_today(self) -> str:
        """Get today's date key"""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    def _get_hour(self) -> str:
        """Get current hour key"""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
    
    def _ensure_day(self, date_key: str):
        """Ensure day entry exists"""
        if date_key not in self.data['daily']:
            self.data['daily'][date_key] = {
                'joins': 0,
                'exits': 0,
                'messages': 0,
                'spam_blocked': 0,
                'bad_language': 0,
                'warnings': 0,
                'mutes': 0,
                'bans': 0,
                'active_users': [],
                'raid_alerts': 0
            }
    
    def _ensure_hour(self, hour_key: str):
        """Ensure hour entry exists"""
        if hour_key not in self.data['hourly']:
            self.data['hourly'][hour_key] = {
                'messages': 0,
                'active_users': []
            }
    
    # ==================== Tracking Methods ====================
    
    def track_join(self, chat_id: int = None):
        """Track a user joining"""
        today = self._get_today()
        self._ensure_day(today)
        self.data['daily'][today]['joins'] += 1
        self._save_data()
    
    def track_exit(self, chat_id: int = None):
        """Track a user leaving"""
        today = self._get_today()
        self._ensure_day(today)
        self.data['daily'][today]['exits'] += 1
        self._save_data()
    
    def track_message(self, user_id: int, chat_id: int = None):
        """Track a message and active user"""
        today = self._get_today()
        hour = self._get_hour()
        
        self._ensure_day(today)
        self._ensure_hour(hour)
        
        # Increment message count
        self.data['daily'][today]['messages'] += 1
        self.data['hourly'][hour]['messages'] += 1
        
        # Track active users (unique)
        if user_id not in self.data['daily'][today]['active_users']:
            self.data['daily'][today]['active_users'].append(user_id)
        if user_id not in self.data['hourly'][hour]['active_users']:
            self.data['hourly'][hour]['active_users'].append(user_id)
        
        self._save_data()
    
    def track_spam_blocked(self, chat_id: int = None):
        """Track spam message blocked"""
        today = self._get_today()
        self._ensure_day(today)
        self.data['daily'][today]['spam_blocked'] += 1
        self._save_data()
    
    def track_bad_language(self, chat_id: int = None):
        """Track bad language detected"""
        today = self._get_today()
        self._ensure_day(today)
        self.data['daily'][today]['bad_language'] += 1
        self._save_data()
    
    def track_warning(self, chat_id: int = None):
        """Track user warning"""
        today = self._get_today()
        self._ensure_day(today)
        self.data['daily'][today]['warnings'] += 1
        self._save_data()
    
    def track_mute(self, chat_id: int = None):
        """Track user mute"""
        today = self._get_today()
        self._ensure_day(today)
        self.data['daily'][today]['mutes'] += 1
        self._save_data()
    
    def track_ban(self, chat_id: int = None):
        """Track user ban"""
        today = self._get_today()
        self._ensure_day(today)
        self.data['daily'][today]['bans'] += 1
        self._save_data()
    
    def track_raid_alert(self, chat_id: int = None):
        """Track raid alert"""
        today = self._get_today()
        self._ensure_day(today)
        self.data['daily'][today]['raid_alerts'] += 1
        self._save_data()
    
    # ==================== Reporting Methods ====================
    
    def get_daily_stats(self, date_key: str = None) -> Dict:
        """Get stats for a specific day"""
        if date_key is None:
            date_key = self._get_today()
        
        self._ensure_day(date_key)
        day_data = self.data['daily'].get(date_key, {})
        
        return {
            'date': date_key,
            'joins': day_data.get('joins', 0),
            'exits': day_data.get('exits', 0),
            'net_members': day_data.get('joins', 0) - day_data.get('exits', 0),
            'messages': day_data.get('messages', 0),
            'spam_blocked': day_data.get('spam_blocked', 0),
            'bad_language': day_data.get('bad_language', 0),
            'warnings': day_data.get('warnings', 0),
            'mutes': day_data.get('mutes', 0),
            'bans': day_data.get('bans', 0),
            'active_users': len(day_data.get('active_users', [])),
            'raid_alerts': day_data.get('raid_alerts', 0)
        }
    
    def get_range_stats(self, days: int = 7) -> Dict:
        """Get aggregated stats for a date range"""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        totals = {
            'period': f"Last {days} days",
            'start_date': start_date.strftime("%Y-%m-%d"),
            'end_date': end_date.strftime("%Y-%m-%d"),
            'joins': 0,
            'exits': 0,
            'net_members': 0,
            'messages': 0,
            'spam_blocked': 0,
            'bad_language': 0,
            'warnings': 0,
            'mutes': 0,
            'bans': 0,
            'active_users': set(),
            'raid_alerts': 0,
            'daily_breakdown': []
        }
        
        current = start_date
        while current <= end_date:
            date_key = current.strftime("%Y-%m-%d")
            day_stats = self.get_daily_stats(date_key)
            
            totals['joins'] += day_stats['joins']
            totals['exits'] += day_stats['exits']
            totals['messages'] += day_stats['messages']
            totals['spam_blocked'] += day_stats['spam_blocked']
            totals['bad_language'] += day_stats['bad_language']
            totals['warnings'] += day_stats['warnings']
            totals['mutes'] += day_stats['mutes']
            totals['bans'] += day_stats['bans']
            totals['raid_alerts'] += day_stats['raid_alerts']
            
            # Track unique active users
            day_data = self.data['daily'].get(date_key, {})
            totals['active_users'].update(day_data.get('active_users', []))
            
            totals['daily_breakdown'].append(day_stats)
            current += timedelta(days=1)
        
        totals['net_members'] = totals['joins'] - totals['exits']
        totals['active_users'] = len(totals['active_users'])
        
        return totals
    
    def get_peak_hours(self, days: int = 7) -> List[Dict]:
        """Get peak activity hours over a period"""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        hour_totals = defaultdict(int)
        
        for hour_key, hour_data in self.data.get('hourly', {}).items():
            try:
                hour_dt = datetime.strptime(hour_key, "%Y-%m-%d-%H")
                hour_dt = hour_dt.replace(tzinfo=timezone.utc)
                if start_date <= hour_dt <= end_date:
                    hour_of_day = hour_dt.hour
                    hour_totals[hour_of_day] += hour_data.get('messages', 0)
            except ValueError:
                continue
        
        # Sort by message count
        sorted_hours = sorted(hour_totals.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {'hour': h, 'hour_str': f"{h:02d}:00 UTC", 'messages': c}
            for h, c in sorted_hours[:5]
        ]
    
    def format_report(self, stats: Dict, include_breakdown: bool = False) -> str:
        """Format stats into a readable message"""
        if 'period' in stats:
            # Range report
            report = f"""📊 <b>Group Analytics</b>
<i>{stats['period']}</i>
<i>{stats['start_date']} to {stats['end_date']}</i>

👥 <b>Members</b>
   ➕ Joined: {stats['joins']}
   ➖ Left: {stats['exits']}
   📈 Net change: {stats['net_members']:+d}

💬 <b>Activity</b>
   📨 Messages: {stats['messages']:,}
   👤 Active users: {stats['active_users']}

🛡️ <b>Moderation</b>
   🚫 Spam blocked: {stats['spam_blocked']}
   🤬 Bad language: {stats['bad_language']}
   ⚠️ Warnings issued: {stats['warnings']}
   🔇 Users muted: {stats['mutes']}
   🔨 Users banned: {stats['bans']}
   🚨 Raid alerts: {stats['raid_alerts']}"""
            
        else:
            # Single day report
            report = f"""📊 <b>Group Analytics</b>
<i>{stats['date']}</i>

👥 <b>Members</b>
   ➕ Joined: {stats['joins']}
   ➖ Left: {stats['exits']}
   📈 Net change: {stats['net_members']:+d}

💬 <b>Activity</b>
   📨 Messages: {stats['messages']:,}
   👤 Active users: {stats['active_users']}

🛡️ <b>Moderation</b>
   🚫 Spam blocked: {stats['spam_blocked']}
   🤬 Bad language: {stats['bad_language']}
   ⚠️ Warnings issued: {stats['warnings']}
   🔇 Users muted: {stats['mutes']}
   🔨 Users banned: {stats['bans']}"""
        
        return report
    
    def cleanup_old_data(self, keep_days: int = 90):
        """Remove data older than specified days"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")
        
        # Clean daily data
        daily_keys = list(self.data.get('daily', {}).keys())
        for key in daily_keys:
            if key < cutoff_str:
                del self.data['daily'][key]
        
        # Clean hourly data
        hourly_keys = list(self.data.get('hourly', {}).keys())
        for key in hourly_keys:
            try:
                if key[:10] < cutoff_str:  # First 10 chars are date
                    del self.data['hourly'][key]
            except:
                continue
        
        self._save_data()
        logger.info(f"Cleaned up analytics data older than {keep_days} days")
