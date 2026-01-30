"""
Night Watchman - OpenAI GPT AI Integration
Uses ChatGPT (GPT) for advanced spam detection with rate limiting.
"""

import base64
import json
import logging
import time
import asyncio
from collections import deque
from typing import Dict, Optional

from config import Config
from redis_manager import RedisManager

logger = logging.getLogger(__name__)

try:
    from openai import AsyncOpenAI
    GPT_AVAILABLE = True
except ImportError:
    GPT_AVAILABLE = False
    logger.warning("openai not installed. GPT scanner disabled.")


class GPTScanner:
    """
    Spam scanner using OpenAI's GPT (ChatGPT) LLM.
    Handles rate limiting for cost control.
    """

    def __init__(self):
        self.config = Config()
        self.api_key = getattr(self.config, 'OPENAI_API_KEY', None) or getattr(self.config, 'GPT_API_KEY', None)
        self.model_name = getattr(self.config, 'GPT_MODEL', 'gpt-4o-mini')
        self.rpm_limit = getattr(self.config, 'GPT_RPM_LIMIT', 30)
        self.enabled = getattr(self.config, 'GPT_ENABLED', True) and GPT_AVAILABLE

        # Rate limiting: Store timestamps of requests
        self._request_timestamps = deque()
        self.client = None

        # Initialize Redis for global rate limiting (required for multi-instance Railway deploys)
        self.redis = RedisManager()

        if self.enabled and self.api_key:
            try:
                self.client = AsyncOpenAI(api_key=self.api_key)
                redis_status = "Redis rate limit: on" if self.redis.enabled else "Redis rate limit: off (in-memory only)"
                logger.info(f"GPT AI scanner initialized (Model: {self.model_name}, {redis_status})")
            except Exception as e:
                logger.error(f"Failed to initialize GPT: {e}")
                self.enabled = False
        elif self.enabled and not self.api_key:
            logger.warning("GPT enabled but no API key found. Disabling.")
            self.enabled = False

    async def _check_rate_limit(self) -> bool:
        """
        Check if we have quota to make a request.
        Uses Redis if available, otherwise falls back to local memory.
        """
        if self.redis.enabled:
            is_limited = await self.redis.check_rate_limit("gpt:rpm", self.rpm_limit, 60)
            return not is_limited

        now = time.time()
        while self._request_timestamps and self._request_timestamps[0] < now - 60:
            self._request_timestamps.popleft()

        if len(self._request_timestamps) < self.rpm_limit:
            self._request_timestamps.append(now)
            return True
        return False

    async def scan_message(self, text: str, user_context: str = "", image_data: Optional[bytes] = None) -> Optional[Dict]:
        """
        Scan a message using GPT.

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
            if not image_data:
                return None

        if not await self._check_rate_limit():
            logger.debug("GPT rate limit reached. Skipping scan.")
            return None

        try:
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

IMAGE ANALYSIS (when an image is attached):
- Read ALL text in the image in ANY language (English, Chinese, etc.). Use OCR-style understanding.
- Flag scam content in images: betting/gambling (e.g. 足球红单, 天天收米, 日赚3千, "earn daily", "click avatar", "DM me to join")
- Flag "DM me" / "private message me" / "click avatar to join group" call-to-actions in images.
- NON-MUDREX SCREENSHOTS: If the image is a screenshot of an app (trading app, betting app, wallet, exchange UI), determine if it is from Mudrex or from another product. Screenshots that are NOT from Mudrex (other exchanges, betting apps, random UIs) shared in this Mudrex community are suspicious and should be flagged as scam/promo unless clearly educational.

Input context: {user_context}

Respond in JSON format ONLY:
{{
  "is_spam": boolean,
  "confidence": float (0.0 to 1.0),
  "category": "string (scam/casino/promo/safe/nsfw/other)",
  "reasoning": "short explanation"
}}
"""
            user_content = system_instruction.format(user_context=user_context or "None")
            if text and len((text or "").strip()) >= 10:
                user_content += f'\n\nMessage: "{text}"'
            elif image_data:
                user_content += '\n\nMessage: [Image only - analyze the attached image for spam, scam, betting/gambling in any language, or non-Mudrex app screenshots.]'

            content_parts = [{"type": "text", "text": user_content}]
            if image_data:
                b64 = base64.b64encode(image_data).decode("utf-8")
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                })

            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": content_parts}]
            )

            result_text = response.choices[0].message.content.strip()

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
                'reason': data.get('reasoning', 'No reason provided')
            }

        except json.JSONDecodeError as e:
            logger.error(f"GPT JSON parse error: {e}")
            return None
        except Exception as e:
            error_msg = str(e).lower()
            if 'quota' in error_msg or 'rate' in error_msg:
                logger.warning(f"GPT quota/rate limit: {e}")
            elif 'api' in error_msg or 'key' in error_msg:
                logger.error(f"GPT API error (check key): {e}")
            else:
                logger.error(f"GPT scan error: {e}")
            return None


_gpt_scanner = None


def get_gpt_scanner() -> GPTScanner:
    global _gpt_scanner
    if _gpt_scanner is None:
        _gpt_scanner = GPTScanner()
    return _gpt_scanner
