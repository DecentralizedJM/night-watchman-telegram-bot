"""
Night Watchman - Pattern Extraction Helper
Uses Gemini to extract spam patterns from natural language descriptions
"""

import json
import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


async def extract_patterns_from_description(gemini_scanner, description: str) -> Optional[Dict]:
    """
    Use Gemini to extract spam patterns from a scam description.
    
    Args:
        gemini_scanner: GeminiScanner instance
        description: Natural language description of the scam
        
    Returns:
        Dict with keywords, regex_patterns, and category or None if extraction failed
    """
    if not gemini_scanner or not gemini_scanner.enabled:
        return None
    
    prompt = f"""Extract spam detection patterns from this scam description:

"{description}"

Analyze this scam and extract:
1. Important keywords (casino names, promo codes, dollar amounts, etc.)
2. Regex patterns that would match similar scams
3. Category of scam

Respond in JSON format ONLY:
{{
  "keywords": ["keyword1", "keyword2", ...],
  "regex_patterns": ["pattern1", "pattern2"],
  "category": "casino|recruitment|trading|phishing|other",
  "confidence": float (0.0-1.0)
}}

Focus on extracting:
- Numbers in casino names (e.g., "88casino" from the description)
- Promo code patterns (e.g., "mega2026")
- Dollar amounts (e.g., "$1000")
- Call-to-action phrases
- URLs or domain patterns
"""
    
    try:
        # Use Gemini's generate_content directly
        import asyncio
        from google import generativeai as genai
        
        response = await asyncio.to_thread(
            gemini_scanner.model.generate_content,
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,  # Low for consistent extraction
                top_p=0.8,
                top_k=40
            ),
            safety_settings=gemini_scanner.safety_settings
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
            'keywords': data.get('keywords', []),
            'regex_patterns': data.get('regex_patterns', []),
            'category': data.get('category', 'other'),
            'confidence': float(data.get('confidence', 0.0))
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error extracting patterns: {e}")
        return None
    except Exception as e:
        logger.error(f"Error extracting patterns: {e}")
        return None


def validate_and_sanitize_patterns(patterns: Dict) -> Dict:
    """
    Validate and sanitize extracted patterns to prevent injection attacks.
    
    Args:
        patterns: Dict with keywords and regex_patterns
        
    Returns:
        Sanitized patterns dict
    """
    sanitized = {
        'keywords': [],
        'regex_patterns': [],
        'category': patterns.get('category', 'other')
    }
    
    # Sanitize keywords (remove dangerous characters)
    for kw in patterns.get('keywords', []):
        if isinstance(kw, str) and len(kw) > 0 and len(kw) < 100:
            # Remove potentially dangerous characters
            clean_kw = re.sub(r'[^\w\s\-$@.]+', '', kw).strip()
            if clean_kw:
                sanitized['keywords'].append(clean_kw.lower())
    
    # Validate regex patterns (test if they compile without errors)
    for pattern in patterns.get('regex_patterns', []):
        if isinstance(pattern, str) and len(pattern) > 0 and len(pattern) < 200:
            try:
                # Test compile
                re.compile(pattern, re.IGNORECASE)
                sanitized['regex_patterns'].append(pattern)
            except re.error:
                logger.warning(f"Invalid regex pattern skipped: {pattern}")
   
    return sanitized
