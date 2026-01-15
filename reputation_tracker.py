"""
Night Watchman - Reputation System
Tracks user reputation points and levels
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from config import Config

logger = logging.getLogger(__name__)


class ReputationTracker:
    """
    Tracks user reputation across the group.
    
    Points system:
    - Daily activity: +5 points
    - Valid spam report: +10 points
    - Warning received: -10 points
    - Muted: -25 points
    - Unmuted (false positive): +15 points
    - Admin enhancement (⭐ emoji): +15 points
    - 7-day streak bonus: +5 points (total: 7x5 + 5 = 40)
    - 30-day streak bonus: +10 points (total: 30x5 + 10 = 160)
    
    Levels (display only - NO perks):
    - Newcomer (0-50)
    - Member (51-200)
    - Trusted (201-500)
    - VIP (501+)
    """
    
    def __init__(self):
        self.config = Config()
        self.data_dir = self.config.ANALYTICS_DATA_DIR
        self.data_file = os.path.join(self.data_dir, "reputation.json")
        self.data = self._load_data()
        self._ensure_structure()
    
    def _ensure_structure(self):
        """Ensure data has correct structure"""
        if 'users' not in self.data:
            self.data['users'] = {}
        if 'daily_activity' not in self.data:
            self.data['daily_activity'] = {}
    
    def _load_data(self) -> Dict:
        """Load reputation data from file"""
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading reputation data: {e}")
        return {}
    
    def _save_data(self):
        """Save reputation data to file"""
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            with open(self.data_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving reputation data: {e}")
    
    def _get_user_key(self, user_id: int) -> str:
        """Get user key for storage"""
        return str(user_id)
    
    def _ensure_user(self, user_id: int, username: str = "", first_name: str = ""):
        """Ensure user exists in data"""
        key = self._get_user_key(user_id)
        if key not in self.data['users']:
            self.data['users'][key] = {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'points': 0,
                'joined': datetime.now(timezone.utc).isoformat(),
                'last_active': datetime.now(timezone.utc).isoformat(),
                'warnings': 0,
                'valid_reports': 0,
                'daily_points_earned': {},  # Track daily gains for abuse prevention
                'last_report_credit': None,  # Cooldown for report credits
                'is_admin_enhanced': False   # IMMUNITY FLAG: Set by admin /enhance command
            }
    
    # ==================== Points Management ====================
    
    # Security: Maximum points a user can earn per day (prevents farming)
    MAX_DAILY_POINTS = 50
    # Security: Minimum seconds between report credits
    REPORT_CREDIT_COOLDOWN_SECONDS = 300  # 5 minutes
    
    def _get_daily_points_earned(self, user_id: int) -> int:
        """Get points earned by user today (for abuse prevention)"""
        key = self._get_user_key(user_id)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        user_data = self.data['users'].get(key, {})
        return user_data.get('daily_points_earned', {}).get(today, 0)
    
    def _record_daily_points(self, user_id: int, points: int):
        """Record points earned today for abuse tracking"""
        if points <= 0:
            return  # Only track gains
        key = self._get_user_key(user_id)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if 'daily_points_earned' not in self.data['users'][key]:
            self.data['users'][key]['daily_points_earned'] = {}
        current = self.data['users'][key]['daily_points_earned'].get(today, 0)
        self.data['users'][key]['daily_points_earned'][today] = current + points
        # Cleanup old days (keep last 7)
        days = list(self.data['users'][key]['daily_points_earned'].keys())
        for d in days:
            if d < (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d"):
                del self.data['users'][key]['daily_points_earned'][d]
    
    def add_points(self, user_id: int, points: int, reason: str = "", 
                   username: str = "", first_name: str = "") -> int:
        """Add points to user, return new total. Enforces daily cap for positive gains."""
        self._ensure_user(user_id, username, first_name)
        key = self._get_user_key(user_id)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # Security: Enforce daily cap for positive point gains
        if points > 0:
            daily_earned = self._get_daily_points_earned(user_id)
            remaining_allowance = max(0, self.MAX_DAILY_POINTS - daily_earned)
            if remaining_allowance == 0:
                logger.warning(f"🛡️ Rep abuse prevention: {user_id} hit daily cap, ignoring +{points} ({reason})")
                return self.data['users'][key]['points']
            # Cap the gain
            actual_points = min(points, remaining_allowance)
            if actual_points < points:
                logger.info(f"🛡️ Rep capped: {user_id} +{actual_points} (requested +{points}, daily limit)")
            points = actual_points
            self._record_daily_points(user_id, points)
        
        self.data['users'][key]['points'] += points
        self.data['users'][key]['last_active'] = datetime.now(timezone.utc).isoformat()
        
        # Track daily points for date-based leaderboards
        if 'daily_points' not in self.data['users'][key]:
            self.data['users'][key]['daily_points'] = {}
        if today not in self.data['users'][key]['daily_points']:
            self.data['users'][key]['daily_points'][today] = 0
        self.data['users'][key]['daily_points'][today] += points
        
        # Update username/name if provided
        if username:
            self.data['users'][key]['username'] = username
        if first_name:
            self.data['users'][key]['first_name'] = first_name
        
        logger.info(f"Rep: {user_id} {points:+d} points ({reason}). Total: {self.data['users'][key]['points']}")
        self._save_data()
        
        return self.data['users'][key]['points']
    
    def remove_points(self, user_id: int, points: int, reason: str = "") -> int:
        """Remove points from user, return new total"""
        return self.add_points(user_id, -abs(points), reason)
    
    def get_points(self, user_id: int) -> int:
        """Get user's current points"""
        key = self._get_user_key(user_id)
        if key in self.data['users']:
            return self.data['users'][key]['points']
        return 0
    
    def set_points(self, user_id: int, points: int) -> int:
        """Set user's points to specific value"""
        self._ensure_user(user_id)
        key = self._get_user_key(user_id)
        self.data['users'][key]['points'] = points
        self._save_data()
        return points
    
    # ==================== Daily Activity ====================
    
    def track_daily_activity(self, user_id: int, username: str = "", first_name: str = "") -> bool:
        """
        Track daily activity. Awards +5 points once per day.
        Also checks for streak bonuses:
        - 7-day streak: +5 bonus points
        - 30-day streak: +10 bonus points
        
        Returns True if points were awarded.
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = self._get_user_key(user_id)
        
        if today not in self.data['daily_activity']:
            self.data['daily_activity'][today] = []
        
        if user_id not in self.data['daily_activity'][today]:
            self.data['daily_activity'][today].append(user_id)
            
            # Award daily points
            self.add_points(user_id, self.config.REP_DAILY_ACTIVE, "daily activity", username, first_name)
            
            # Check for streak bonuses
            streak_days = self._get_active_streak(user_id)
            
            # 7-day streak bonus
            if streak_days == 7:
                self.add_points(user_id, self.config.REP_7DAY_STREAK_BONUS, "7-day active streak bonus", username, first_name)
                logger.info(f"🔥 User {user_id} earned 7-day streak bonus!")
            
            # 30-day streak bonus
            elif streak_days == 30:
                self.add_points(user_id, self.config.REP_30DAY_STREAK_BONUS, "30-day active streak bonus", username, first_name)
                logger.info(f"🔥🔥 User {user_id} earned 30-day streak bonus!")
            
            return True
        
        # Still update last_active even if no points
        self._ensure_user(user_id, username, first_name)
        self.data['users'][key]['last_active'] = datetime.now(timezone.utc).isoformat()
        self._save_data()
        return False
    
    def _get_active_streak(self, user_id: int) -> int:
        """
        Calculate current consecutive daily activity streak.
        Returns number of consecutive days user has been active.
        """
        today = datetime.now(timezone.utc).date()
        streak = 0
        
        # Check backwards from today
        for i in range(365):  # Max check 1 year back
            check_date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            
            if check_date in self.data['daily_activity']:
                if user_id in self.data['daily_activity'][check_date]:
                    streak += 1
                else:
                    break  # Streak broken
            else:
                break  # No activity that day
        
        return streak
    
    def admin_enhancement(self, user_id: int, username: str = "", first_name: str = "") -> int:
        """
        Admin enhancement: Award +15 points when admin reacts with any emoji.
        Max once per message (deduplication handled in bot).
        Returns new total points.
        """
        points_awarded = self.add_points(
            user_id, 
            self.config.REP_ADMIN_ENHANCEMENT, 
            "admin enhancement", 
            username, 
            first_name
        )

        # Mark as enhanced (Immunity from most bans)
        key = self._get_user_key(user_id)
        self.data['users'][key]['is_admin_enhanced'] = True
        self._save_data()
        
        logger.info(f"⭐ Admin enhanced user {user_id} with +{self.config.REP_ADMIN_ENHANCEMENT} points (IMMUNITY GRANTED)")
        return points_awarded
    
    def is_immune(self, user_id: int) -> bool:
        """
        Check if user is immune to standard bans.
        Immunity criteria:
        1. Reputation > 10 points
        2. OR Explicitly enhanced by admin (is_admin_enhanced=True)
        """
        key = self._get_user_key(user_id)
        if key not in self.data['users']:
            return False
            
        user_data = self.data['users'][key]
        
        # Check explicit enhancement
        if user_data.get('is_admin_enhanced', False):
            return True
            
        # Check points threshold
        points = user_data.get('points', 0)
        return points > 10
    
    # ==================== Level System ====================
    
    def get_level(self, user_id: int) -> Tuple[str, str, int]:
        """
        Get user's level based on points.
        Returns: (level_name, emoji, next_level_points)
        """
        points = self.get_points(user_id)
        
        if points >= self.config.REP_LEVEL_VIP:
            return "VIP", "💎", 0  # Max level
        elif points >= self.config.REP_LEVEL_TRUSTED:
            return "Trusted", "⭐", self.config.REP_LEVEL_VIP
        elif points >= self.config.REP_LEVEL_MEMBER:
            return "Member", "🌟", self.config.REP_LEVEL_TRUSTED
        else:
            return "Newcomer", "🆕", self.config.REP_LEVEL_MEMBER
    
    def get_level_info(self, user_id: int) -> Dict:
        """Get detailed level info for user"""
        points = self.get_points(user_id)
        level_name, emoji, next_level = self.get_level(user_id)
        
        return {
            'points': points,
            'level': level_name,
            'emoji': emoji,
            'next_level_at': next_level,
            'points_to_next': max(0, next_level - points) if next_level > 0 else 0
        }
    
    def get_user_rep(self, user_id: int) -> Dict:
        """
        Get user's reputation data including points, level, and message count.
        Used for spam detection (money emoji check for new users).
        """
        key = self._get_user_key(user_id)
        user_data = self.data['users'].get(key, {})
        
        points = user_data.get('points', 0)
        level_name, emoji, next_level = self.get_level(user_id)
        
        # Count total messages from daily activity
        total_messages = 0
        if 'daily_activity' in user_data:
            for day_data in user_data['daily_activity'].values():
                total_messages += day_data.get('messages', 0)
        
        return {
            'user_id': user_id,
            'points': points,
            'level': level_name,
            'emoji': emoji,
            'warnings': user_data.get('warnings', 0),
            'total_messages': total_messages,
            'joined': user_data.get('joined'),
            'last_active': user_data.get('last_active')
        }
    
    def can_post_links(self, user_id: int) -> bool:
        """DEPRECATED: Links allowed for everyone now. Kept for compatibility."""
        return True  # No restrictions based on reputation
    
    def can_forward(self, user_id: int) -> bool:
        """DEPRECATED: Forwards controlled by admin setting only. Kept for compatibility."""
        return False  # Admins only can forward (controlled in main bot)
    
    def is_trusted(self, user_id: int) -> bool:
        """DEPRECATED: No reputation-based trust. Kept for compatibility."""
        return True  # Everyone is trusted equally
    
    # ==================== Event Tracking ====================
    
    def on_warning(self, user_id: int, username: str = "", first_name: str = "") -> int:
        """Called when user receives a warning"""
        self._ensure_user(user_id, username, first_name)
        key = self._get_user_key(user_id)
        self.data['users'][key]['warnings'] += 1
        self._save_data()
        return self.remove_points(user_id, abs(self.config.REP_WARNING_PENALTY), "warning received")
    
    def on_mute(self, user_id: int) -> int:
        """Called when user is muted"""
        return self.remove_points(user_id, abs(self.config.REP_MUTE_PENALTY), "muted")
    
    def on_unmute(self, user_id: int) -> int:
        """Called when user is unmuted (false positive)"""
        return self.add_points(user_id, self.config.REP_UNMUTE_BONUS, "unmuted (false positive)")
    
    def on_valid_report(self, user_id: int, username: str = "", first_name: str = "") -> int:
        """Called when user's spam report leads to action. Enforces cooldown to prevent abuse."""
        self._ensure_user(user_id, username, first_name)
        key = self._get_user_key(user_id)
        
        # Security: Enforce cooldown between report credits
        now = datetime.now(timezone.utc)
        last_credit_str = self.data['users'][key].get('last_report_credit')
        if last_credit_str:
            try:
                last_credit = datetime.fromisoformat(last_credit_str)
                elapsed = (now - last_credit).total_seconds()
                if elapsed < self.REPORT_CREDIT_COOLDOWN_SECONDS:
                    logger.info(f"🛡️ Report credit cooldown: {user_id} must wait {int(self.REPORT_CREDIT_COOLDOWN_SECONDS - elapsed)}s")
                    return self.get_points(user_id)  # No points awarded
            except (ValueError, TypeError):
                pass  # Invalid date, proceed
        
        self.data['users'][key]['valid_reports'] += 1
        self.data['users'][key]['last_report_credit'] = now.isoformat()
        self._save_data()
        return self.add_points(user_id, self.config.REP_VALID_REPORT, "valid spam report", username, first_name)
    
    # ==================== Leaderboard ====================
    
    def get_leaderboard(self, limit: int = 10, days: int = 0) -> List[Dict]:
        """
        Get top users by reputation.
        
        Args:
            limit: Number of users to return
            days: If 0, return lifetime leaderboard. If > 0, return points earned in last N days.
        """
        users = []
        today = datetime.now(timezone.utc)
        
        for key, user_data in self.data.get('users', {}).items():
            if days > 0:
                # Calculate points earned in the last N days
                daily_points = user_data.get('daily_points', {})
                period_points = 0
                for i in range(days):
                    date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
                    period_points += daily_points.get(date_str, 0)
                points = period_points
            else:
                # Lifetime points
                points = user_data.get('points', 0)
            
            users.append({
                'user_id': user_data.get('user_id'),
                'username': user_data.get('username', ''),
                'first_name': user_data.get('first_name', 'Unknown'),
                'points': points,
                'level': self.get_level(user_data.get('user_id', 0))[0],
                'emoji': self.get_level(user_data.get('user_id', 0))[1]
            })
        
        # Sort by points descending, filter out zero points for date-based
        if days > 0:
            users = [u for u in users if u['points'] > 0]
        users.sort(key=lambda x: x['points'], reverse=True)
        return users[:limit]
    
    def format_leaderboard(self, limit: int = 10, days: int = 0) -> str:
        """
        Format leaderboard as message.
        
        Args:
            limit: Number of users to show
            days: If 0, lifetime. If > 0, last N days.
        """
        leaders = self.get_leaderboard(limit, days)
        
        if not leaders:
            if days > 0:
                return f"📊 <b>Leaderboard (Last {days} days)</b>\n\nNo activity in this period!"
            return "📊 <b>Leaderboard</b>\n\nNo users yet!"
        
        if days > 0:
            msg = f"🏆 <b>Reputation Leaderboard</b>\n<i>Last {days} days</i>\n\n"
        else:
            msg = "🏆 <b>Reputation Leaderboard</b>\n<i>All time</i>\n\n"
        
        medals = ["🥇", "🥈", "🥉"]
        for i, user in enumerate(leaders):
            rank = medals[i] if i < 3 else f"{i+1}."
            name = user['first_name']
            if user['username']:
                name = f"@{user['username']}"
            
            msg += f"{rank} {user['emoji']} <b>{name}</b> - {user['points']} pts\n"
        
        return msg
    
    def format_user_rep(self, user_id: int, username: str = "", first_name: str = "") -> str:
        """Format user reputation as message"""
        self._ensure_user(user_id, username, first_name)
        info = self.get_level_info(user_id)
        key = self._get_user_key(user_id)
        user_data = self.data['users'].get(key, {})
        
        name = first_name or "User"
        if username:
            name = f"@{username}"
        
        msg = f"""⭐ <b>Reputation: {name}</b>

{info['emoji']} Level: <b>{info['level']}</b>
📊 Points: <b>{info['points']}</b>"""
        
        if info['points_to_next'] > 0:
            msg += f"\n📈 Next level: {info['points_to_next']} more points"
        
        msg += f"""

📋 Stats:
• Warnings: {user_data.get('warnings', 0)}
• Valid reports: {user_data.get('valid_reports', 0)}"""
        
        return msg
    
    # ==================== Cleanup ====================
    
    def cleanup_old_activity(self, keep_days: int = 30):
        """Remove old daily activity data"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")
        
        keys_to_remove = [
            key for key in self.data.get('daily_activity', {}).keys()
            if key < cutoff_str
        ]
        
        for key in keys_to_remove:
            del self.data['daily_activity'][key]
        
        if keys_to_remove:
            self._save_data()
            logger.info(f"Cleaned up {len(keys_to_remove)} old activity records")
