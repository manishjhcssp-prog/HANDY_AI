"""
Tests for KeyManager: multi-key registration, round-robin rotation,
cooldown periods, rate limiting (HTTP 429), quota exhaustion, and key masking.
"""

import time
import pytest
from jarvis.brain.key_manager import KeyManager, KeyStatus
from config.settings import mask_key


def test_key_masking():
    assert mask_key("sk-or-v1-abcdef1234567890") == "sk-or...7890"
    assert mask_key("short") == "********"
    assert mask_key("") == "none"
    assert mask_key(None) == "none"


def test_multi_key_registration_and_round_robin():
    km = KeyManager(default_cooldown_seconds=5.0)
    keys = ["key_alpha_12345", "key_beta_67890"]
    km.register_keys("openrouter", keys)

    assert km.get_key_count("openrouter") == 2

    # First fetch -> key_alpha
    k1 = km.get_available_key("openrouter")
    assert k1 is not None
    assert k1.key == "key_alpha_12345"

    # Second fetch -> key_beta (round robin)
    k2 = km.get_available_key("openrouter")
    assert k2 is not None
    assert k2.key == "key_beta_67890"

    # Third fetch -> key_alpha again
    k3 = km.get_available_key("openrouter")
    assert k3 is not None
    assert k3.key == "key_alpha_12345"


def test_rate_limiting_cooldown_and_recovery():
    km = KeyManager(default_cooldown_seconds=0.2)
    keys = ["key_1_test", "key_2_test"]
    km.register_keys("groq", keys)

    # Mark key 1 as rate limited with 0.1s cooldown
    km.mark_rate_limited("groq", "key_1_test", retry_after=0.1)

    # Next fetch must skip key 1 and give key 2
    k = km.get_available_key("groq")
    assert k is not None
    assert k.key == "key_2_test"

    # Before cooldown expires, key 1 is still unavailable
    assert not km._find_key_info("groq", "key_1_test").is_available

    # Wait for cooldown to expire
    time.sleep(0.15)

    # Now key 1 must be available again
    assert km._find_key_info("groq", "key_1_test").is_available


def test_invalid_key_handling():
    km = KeyManager()
    km.register_keys("gemini", ["valid_key_1", "bad_key_2"])

    # Mark bad_key_2 as invalid (401/403)
    km.mark_invalid("gemini", "bad_key_2", reason="Invalid API Key")

    info = km._find_key_info("gemini", "bad_key_2")
    assert info.status == KeyStatus.INVALID
    assert not info.is_available

    # Repeated calls should only return valid_key_1
    for _ in range(3):
        k = km.get_available_key("gemini")
        assert k is not None
        assert k.key == "valid_key_1"


def test_quota_exhausted_handling():
    km = KeyManager()
    km.register_keys("sarvam", ["key_sarvam_1"])

    km.mark_quota_exhausted("sarvam", "key_sarvam_1")
    assert km.get_available_key("sarvam") is None
