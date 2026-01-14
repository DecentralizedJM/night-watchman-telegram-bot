"""
Night Watchman - Google Gemini AI Integration
Uses Gemini (new SDK) for advanced spam detection with rate limiting.
"""

import os
import logging
import time
import json
import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Tuple, Optional

from config import Config

logger = logging.getLogger(__name__)

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-genai not installed. Gemini scanner disabled.")

class GeminiScanner:
    """
    Spam scanner using Google's Gemini LLM (new SDK).
    Handles rate limiting to stay within free tier usage.
    """
    
    def __init__(self):
        self.config = Config()
        self.api_key = self.config.GEMINI_API_KEY
        self.model_name = getattr(self.config, 'GEMINI_MODEL', 'gemini-2.5-flash')
        self.rpm_limit = getattr(self.config, 'GEMINI_RPM_LIMIT', 10)
        self.enabled = getattr(self.config, 'GEMINI_ENABLED', False) and GEMINI_AVAILABLE
        
        # Rate limiting: Store timestamps of requests
        self._request_timestamps = deque()
        self.client = None
        
        if self.enabled and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"✨ Gemini AI scanner initialized (Model: {self.model_name})")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
                self.enabled = False
        elif self.enabled and not self.api_key:
            logger.warning("⚠️ Gemini enabled but no API key found. Disabling.")
            self.enabled = False
            
    def _check_rate_limit(self) -> bool:
        """
        Check if we have quota to make a request.
        Removes timestamps older than 60 seconds.
        Returns True if allowed, False if rate limited.
        """
        now = time.time()
        
        # Remove timestamps older than 60 seconds
        while self._request_timestamps and self._request_timestamps[0] < now - 60:
            self._request_timestamps.popleft()
            
        # Check if we have room
        if len(self._request_timestamps) < self.rpm_limit:
            self._request_timestamps.append(now)
            return True
            
        return False
        
    async def scan_message(self, text: str, user_context: str = "", image_data: Optional[bytes] = None) -> Optional[Dict]:
        """
        Scan a message using Gemini.
        
        Args:
            text: Message text
            user_context: Additional context about user (e.g. "New user, joined 5 min ago")
            image_data: Optional image data (bytes) for image-based spam detection
            
        Returns:
            Dict with keys: is_spam (bool), confidence (float), reasoning (str), reason (str)
            OR None if scan was skipped (rate limit, error, disabled)
        """
        if not self.enabled or not self.client:
            return None
            
        if not text or len(text) < 10:
            # If we have image data but no text, still scan
            if not image_data:
                return None
        
        # Check rate limit
        if not self._check_rate_limit():
            logger.debug("⏳ Gemini rate limit reached. Skipping scan.")
            return None
            
        try:
            # Construct prompt
            system_instruction = """You are a Telegram Group Moderator Bot. 
Analyze the following message for SPAM, SCAM, PHISHING, or MALICIOUS content.

Context: Crypto trading community (Mudrex).
Strictly identify:
- Crypto scams (doubling money, fake investment schemes)
- Casino/gambling spam (promo codes, bonuses, fake wins)
- Phishing links (wallet drainers, fake airdrops)
- Recruitment scams (fake job offers asking to DM)
- Unsolicited promotion/ads
- NSFW/Adult content

Input context: {user_context}

Respond in JSON format ONLY:
{{
  "is_spam": boolean,
  "confidence": float (0.0 to 1.0),
  "category": "string (scam/casino/promo/safe/nsfw/other)",
  "reasoning": "short explanation"
}}
"""
            prompt = f"{system_instruction}\n\nMessage: \"{text}\"" if text else system_instruction
            
            # Prepare contents - text and/or image
            contents = [prompt]
            if image_data:
                from google.genai import types
                image_part = types.Part.from_bytes(data=image_data, mime_type="image/jpeg")
                contents = [image_part, prompt]
            
            # Generate content using new API
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=contents
            )
            
            result_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
                
            data = json.loads(result_text.strip())
            
            return {
                'is_spam': data.get('is_spam', False),
                'confidence': float(data.get('confidence', 0.0)),
                'reasoning': data.get('reasoning', 'No reason provided'),
                'reason': data.get('reasoning', 'No reason provided')  # Alias for compatibility
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Gemini JSON parse error: {e}")
            return None
        except Exception as e:
            error_msg = str(e).lower()
            if 'quota' in error_msg or 'rate' in error_msg:
                logger.warning(f"⏳ Gemini quota/rate limit: {e}")
            elif 'api' in error_msg or 'key' in error_msg:
                logger.error(f"❌ Gemini API error (check key): {e}")
            else:
                logger.error(f"❌ Gemini scan error: {e}")
            return None

# Global instance
_gemini_scanner = None

def get_gemini_scanner() -> GeminiScanner:
    global _gemini_scanner
    if _gemini_scanner is None:
        _gemini_scanner = GeminiScanner()
    return _gemini_scanner