"""
Night Watchman - Google Gemini AI Integration
Uses Gemini Pro (Free Tier) for advanced spam detection with rate limiting.
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
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai not installed. Gemini scanner disabled.")

class GeminiScanner:
    """
    Spam scanner using Google's Gemini LLM.
    Handles rate limiting to stay within free tier usage.
    """
    
    def __init__(self):
        self.config = Config()
        self.api_key = self.config.GEMINI_API_KEY
        self.model_name = getattr(self.config, 'GEMINI_MODEL', 'gemini-pro')
        self.rpm_limit = getattr(self.config, 'GEMINI_RPM_LIMIT', 10)
        self.enabled = getattr(self.config, 'GEMINI_ENABLED', False) and GEMINI_AVAILABLE
        
        # Rate limiting: Store timestamps of requests
        self._request_timestamps = deque()
        self.model = None
        
        if self.enabled and self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                
                # Safety settings - allow content for analysis, don't block too aggressively
                # We want to DETECT spam/harm, not have the API block the input
                self.safety_settings = {
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
                
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
        
    async def scan_message(self, text: str, user_context: str = "") -> Optional[Dict]:
        """
        Scan a message using Gemini.
        
        Args:
            text: Message text
            user_context: Additional context about user (e.g. "New user, joined 5 min ago")
            
        Returns:
            Dict with keys: is_spam (bool), confidence (float), reasoning (str)
            OR None if scan was skipped (rate limit, error, disabled)
        """
        if not self.enabled or not self.model:
            return None
            
        if not text or len(text) < 10:
            return None
            
        # Check rate limit
        if not self._check_rate_limit():
            logger.warning("⏳ Gemini rate limit reached. Skipping scan.")
            return None
            
        try:
            # Construct prompt
            system_instruction = """You are a Telegram Group Moderator Bot. 
Analyze the following message for SPAM, SCAM, PHISHING, or MALICIOUS content.

Context: Crypto trading community (Mudrex).
Strictly identify:
- Crypto scams (doubling money, fake investment schemes)
- Phishing links (wallet drainers, fake airsrops)
- Recruitment scams (fake job offers asking to DM)
- unsolicited promotion/ads
- NSFW/Adult content

Input context: {user_context}

Respond in JSON format ONLY:
{
  "is_spam": boolean,
  "confidence": float (0.0 to 1.0),
  "category": "string (scam/promo/safe/nsfw/other)",
  "reasoning": "short explanation"
}
"""
            prompt = f"{system_instruction}\n\nMessage: \"{text}\""
            
            # Run in executor to avoid blocking event loop
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,  # Low temperature for consistent classification
                    top_p=0.8,
                    top_k=40
                ),
                safety_settings=self.safety_settings
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
                'reasoning': data.get('reasoning', 'No reason provided')
            }
            
        except Exception as e:
            logger.error(f"Gemini scan error: {e}")
            return None

# Global instance
_gemini_scanner = None

def get_gemini_scanner() -> GeminiScanner:
    global _gemini_scanner
    if _gemini_scanner is None:
        _gemini_scanner = GeminiScanner()
    return _gemini_scanner
