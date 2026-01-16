"""
Night Watchman - Hugging Face Classifier Integration
Zero-shot spam classification using Hugging Face Inference API
"""

import os
import logging
import asyncio
from typing import Optional, Dict
import httpx

from config import Config

logger = logging.getLogger(__name__)


class HuggingFaceClassifier:
    """
    Spam classifier using Hugging Face Inference API.
    Uses zero-shot classification for detecting novel scam patterns.
    """
    
    def __init__(self):
        self.config = Config()
        self.api_key = os.getenv("HUGGINGFACE_API_KEY")
        self.enabled = bool(self.api_key)
        
        # Using BART Large MNLI for zero-shot classification
        self.api_url = "https://router.huggingface.co/hf-inference/models/facebook/bart-large-mnli"
        
        # Candidate labels for classification
        self.spam_labels = [
            "casino gambling spam",
            "recruitment job scam", 
            "trading investment scam",
            "phishing malicious link",
            "legitimate crypto discussion",
            "normal conversation"
        ]
        
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        
        if self.enabled:
            logger.info("🤗 Hugging Face classifier initialized")
        else:
            logger.warning("⚠️ Hugging Face API key not found. HF classifier disabled.")
    
    async def classify(self, text: str) -> Optional[Dict]:
        """
        Classify text using zero-shot classification.
        
        Args:
            text: Message text to classify
            
        Returns:
            Dict with labels and scores, or None if classification failed
        """
        if not self.enabled:
            return None
            
        if not text or len(text) < 10:
            return None
        
        try:
            # Truncate text if too long (HF has input limits)
            max_length = 512
            if len(text) > max_length:
                text = text[:max_length]
            
            payload = {
                "inputs": text,
                "parameters": {
                    "candidate_labels": self.spam_labels,
                    "multi_label": False  # Single label classification
                }
            }
            
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            response = await self.client.post(
                self.api_url,
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Handle list response (sometimes returned by HF API)
                if isinstance(result, list):
                    if not result:
                        return None
                    # If it's a list, the first item is usually the result dict
                    result = result[0]
                    # Check if we still have a dict
                    if not isinstance(result, dict):
                        logger.warning(f"Unexpected HF response format inside list: {type(result)}")
                        return None
                
                # Parse response
                labels = result.get('labels', [])
                scores = result.get('scores', [])
                
                if labels and scores:
                    top_label = labels[0]
                    top_score = scores[0]
                    
                    # Determine if spam
                    spam_categories = [
                        "casino gambling spam",
                        "recruitment job scam",
                        "trading investment scam",
                        "phishing malicious link"
                    ]
                    
                    is_spam = top_label in spam_categories and top_score > 0.6
                    
                    return {
                        'is_spam': is_spam,
                        'confidence': top_score,
                        'category': top_label,
                        'all_labels': labels[:3],  # Top 3
                        'all_scores': scores[:3]
                    }
            elif response.status_code == 503:
                # Model loading - this is normal for free tier
                logger.debug(f"⏳ HF model loading, skipping classification")
                return None
            else:
                logger.warning(f"HF API error {response.status_code}: {response.text[:100]}")
                
        except httpx.TimeoutException:
            logger.debug("⏳ HF API timeout")
        except Exception as e:
            error_msg = str(e).lower()
            if 'rate' in error_msg or 'limit' in error_msg:
                logger.debug(f"⏳ HF rate limit")
            else:
                logger.error(f"HF classification error: {e}")
        
        return None
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Global instance
_hf_classifier: Optional[HuggingFaceClassifier] = None


def get_hf_classifier() -> HuggingFaceClassifier:
    """Get or create the global HF classifier instance."""
    global _hf_classifier
    if _hf_classifier is None:
        _hf_classifier = HuggingFaceClassifier()
    return _hf_classifier
