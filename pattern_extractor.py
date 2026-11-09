"""
Local pattern extraction for /newscam.
Pulls keywords and a category from an admin description. No model API.
"""

import re
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

_CATEGORY_HINTS = (
    ("casino", ("casino", "spin", "jackpot", "betting", "1win", "bonus code")),
    ("recruitment", ("recruit", "hiring", "per day", "task", "salary")),
    ("trading", ("profit", "forex", "signal", "mt4", "mt5", "roi")),
    ("phishing", ("seed", "private key", "wallet", "apk", "verify")),
)


def extract_patterns_locally(description: str) -> Dict:
    """Extract keywords, a couple of regexes, and a category from plain text."""
    text = description or ""
    keywords: List[str] = []

    for match in re.findall(r"https?://[^\s]+|www\.[^\s]+", text, flags=re.I):
        keywords.append(match.lower().rstrip(".,)"))

    for match in re.findall(r"@[a-zA-Z0-9_]{4,}", text):
        keywords.append(match.lower())

    for match in re.findall(r"\$\d[\d,]*(?:\.\d+)?|\d+\s?%", text):
        keywords.append(match.lower().replace(" ", ""))

    for match in re.findall(r"\b[a-zA-Z]*\d{2,}[a-zA-Z0-9]*\b", text):
        if len(match) >= 4:
            keywords.append(match.lower())

    for match in re.findall(r"\b[a-zA-Z]{5,}\b", text):
        word = match.lower()
        if word not in {"they're", "theyre", "promoting", "people", "about", "where", "which"}:
            keywords.append(word)

    # Preserve order, drop duplicates
    seen = set()
    unique = []
    for keyword in keywords:
        if keyword not in seen:
            seen.add(keyword)
            unique.append(keyword)

    regexes = []
    for keyword in unique:
        if re.search(r"\d", keyword) and re.search(r"[a-z]", keyword) and len(keyword) <= 24:
            regexes.append(re.escape(keyword))
        if len(regexes) >= 5:
            break

    lowered = text.lower()
    category = "other"
    for name, hints in _CATEGORY_HINTS:
        if any(hint in lowered for hint in hints):
            category = name
            break

    logger.info(f"Local scam patterns: {len(unique)} keywords, category={category}")
    return {
        "keywords": unique[:15],
        "regex_patterns": regexes,
        "category": category,
        "confidence": 0.6 if unique else 0.2,
    }


def validate_and_sanitize_patterns(patterns: Dict) -> Dict:
    """Validate and sanitize extracted patterns to prevent injection attacks."""
    sanitized = {
        "keywords": [],
        "regex_patterns": [],
        "category": patterns.get("category", "other"),
    }

    for keyword in patterns.get("keywords", []):
        if isinstance(keyword, str) and 0 < len(keyword) < 100:
            clean = re.sub(r"[^\w\s\-$@./:]+", "", keyword).strip()
            if clean:
                sanitized["keywords"].append(clean.lower())

    for pattern in patterns.get("regex_patterns", []):
        if isinstance(pattern, str) and 0 < len(pattern) < 200:
            try:
                re.compile(pattern)
                sanitized["regex_patterns"].append(pattern)
            except re.error:
                logger.warning(f"Dropped invalid regex: {pattern}")

    return sanitized
