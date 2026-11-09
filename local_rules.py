"""Local Mudrex and forward rules. No external model APIs."""

import re
from typing import Dict, Iterable, Optional

OFFICIAL_USERNAMES = {
    "mudrex",
    "officialmudrex",
    "mudrex_nightwatchman_bot",
    "nightwatchman_bot",
}

_SEED_PATTERNS = (
    r"\bseed phrase\b",
    r"\brecovery phrase\b",
    r"\bprivate key\b",
    r"\bsecret phrase\b",
    r"\b12[\s-]?words\b",
    r"\btwelve words\b",
    r"\bmnemonic\b",
)

_SUPPORT_PATTERNS = (
    r"(i am|i'm|this is|im).{0,24}mudrex\s+(support|admin|official)",
    r"mudrex\s+(support|admin).{0,40}(dm|inbox|whatsapp|telegram|message)",
    r"(dm|inbox|whatsapp).{0,30}mudrex\s+(support|admin)",
)


def check_account_threats(message: str) -> Dict:
    """Instant-ban signals that do not need a language model."""
    result = {"instant_ban": False, "reasons": [], "triggers": []}
    if not message:
        return result

    text = message.lower()

    for pattern in _SEED_PATTERNS:
        if re.search(pattern, text):
            result["instant_ban"] = True
            result["reasons"].append("Asks for a seed phrase or private key")
            result["triggers"].append("seed_phrase")
            return result

    for pattern in _SUPPORT_PATTERNS:
        if re.search(pattern, text):
            result["instant_ban"] = True
            result["reasons"].append("Mudrex support impersonation")
            result["triggers"].append("support_impersonation")
            return result

    if re.search(r"https?://\S+\.apk\b", text) or re.search(r"\S+\.apk\b", text):
        if "play.google.com" not in text and "apps.apple.com" not in text:
            result["instant_ban"] = True
            result["reasons"].append("APK download outside official stores")
            result["triggers"].append("apk_sideload")
            return result

    return result


def is_mudrex_lookalike(username: Optional[str], official: Optional[Iterable[str]] = None) -> bool:
    """True when a username imitates Mudrex and is not an official account."""
    if not username:
        return False
    allowed = {name.lower().lstrip("@") for name in (official or OFFICIAL_USERNAMES)}
    handle = username.lower().lstrip("@")
    if handle in allowed:
        return False
    compact = re.sub(r"[^a-z0-9]", "", handle)
    if "mudrex" in compact or "mudrexx" in compact or "rnudrex" in compact:
        return True
    return bool(re.search(r"mudr[e3]x", compact))


def forward_source_allowed(message: Dict, allowlist: Iterable[str]) -> bool:
    """True when a forward comes from a configured channel username or id."""
    allowed = {str(item).lower().lstrip("@") for item in allowlist if item}
    if not allowed or not isinstance(message, dict):
        return False

    origin = message.get("forward_origin") or {}
    chat = {}
    if isinstance(origin, dict):
        chat = origin.get("chat") or {}
    if not chat:
        chat = message.get("forward_from_chat") or {}
    if not isinstance(chat, dict):
        return False

    username = str(chat.get("username") or "").lower()
    chat_id = str(chat.get("id") or "")
    return (username and username in allowed) or (chat_id and chat_id in allowed)
