"""Local moderation rules that do not call a model API."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from local_rules import check_account_threats, forward_source_allowed, is_mudrex_lookalike
from pattern_extractor import extract_patterns_locally, validate_and_sanitize_patterns
from scam_memory import ScamMemory


def test_seed_phrase_is_instant_ban():
    result = check_account_threats("Send me your seed phrase so I can fix the Mudrex withdrawal")
    assert result["instant_ban"] is True
    assert "seed_phrase" in result["triggers"]


def test_support_impersonation_is_instant_ban():
    result = check_account_threats("I am Mudrex support, DM me on telegram to verify your account")
    assert result["instant_ban"] is True
    assert "support_impersonation" in result["triggers"]


def test_store_links_are_not_apk_bans():
    result = check_account_threats("Get the app at https://play.google.com/store/apps")
    assert result["instant_ban"] is False


def test_sideload_apk_is_instant_ban():
    result = check_account_threats("Install https://files.example/mudrex.apk for the bonus")
    assert result["instant_ban"] is True
    assert "apk_sideload" in result["triggers"]


def test_official_username_is_not_a_lookalike():
    assert is_mudrex_lookalike("officialmudrex") is False
    assert is_mudrex_lookalike("mudrex_support") is True
    assert is_mudrex_lookalike("mudr3x_help") is True


def test_known_channel_forward_is_allowed():
    message = {"forward_origin": {"type": "channel", "chat": {"id": -1001, "username": "officialmudrex"}}}
    assert forward_source_allowed(message, ["officialmudrex"]) is True
    assert forward_source_allowed(message, ["someotherchannel"]) is False


def test_newscam_extracts_without_an_api():
    patterns = validate_and_sanitize_patterns(
        extract_patterns_locally("They're promoting 88casino with code mega2026 for $1000")
    )
    assert "88casino" in patterns["keywords"]
    assert patterns["category"] == "casino"
    assert patterns["regex_patterns"]


def test_scam_memory_overlap_without_embeddings(tmp_path):
    memory = ScamMemory(str(tmp_path), embedder=None)
    assert memory.add("Install the bonus apk and send your recovery phrase today")
    score, kind = memory.score("Please send your recovery phrase and the bonus apk now")
    assert kind == "overlap"
    assert score >= 0.5
