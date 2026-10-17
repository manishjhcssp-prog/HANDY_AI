"""
JARVIS AI - Multi-Key Manager
Manages multiple API keys per provider, tracking health, rate limits,
cooldown periods, and quota exhaustion with automatic rotation.
"""

import time
import logging
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from config.settings import mask_key

logger = logging.getLogger("JARVIS.KeyManager")


class KeyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COOLDOWN = "COOLDOWN"          # Temporary rate limit (HTTP 429)
    EXHAUSTED = "EXHAUSTED"        # Quota depleted (monthly / daily limit)
    INVALID = "INVALID"            # Auth failure (HTTP 401 / 403)


@dataclass
class KeyInfo:
    provider: str
    key: str
    key_id: str                   # E.g. "openrouter_key_1"
    masked: str = ""
    status: KeyStatus = KeyStatus.ACTIVE
    cooldown_until: float = 0.0
    failure_count: int = 0
    success_count: int = 0
    last_error: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.masked:
            self.masked = mask_key(self.key)

    @property
    def is_available(self) -> bool:
        if self.status == KeyStatus.INVALID or self.status == KeyStatus.EXHAUSTED:
            return False
        if self.status == KeyStatus.COOLDOWN:
            if time.time() >= self.cooldown_until:
                # Cooldown expired, restore to active
                self.status = KeyStatus.ACTIVE
                self.cooldown_until = 0.0
                logger.info(f"[{self.provider}] Cooldown expired for key {self.masked}. Restoring to ACTIVE.")
                return True
            return False
        return True


class KeyManager:
    """
    Manages key pools across providers with round-robin selection and intelligent health tracking.
    """

    def __init__(self, default_cooldown_seconds: float = 60.0):
        self.default_cooldown = default_cooldown_seconds
        # provider -> list of KeyInfo
        self._pools: Dict[str, List[KeyInfo]] = {}
        # provider -> current rotation index
        self._rotation_index: Dict[str, int] = {}

    def register_keys(self, provider: str, keys: List[str]) -> None:
        """Register a list of raw keys for a specific provider."""
        provider = provider.lower()
        if provider not in self._pools:
            self._pools[provider] = []
            self._rotation_index[provider] = 0

        existing_raw = {k.key for k in self._pools[provider]}
        for idx, k in enumerate(keys, start=len(self._pools[provider]) + 1):
            cleaned = k.strip() if k else ""
            if cleaned and cleaned not in existing_raw:
                info = KeyInfo(
                    provider=provider,
                    key=cleaned,
                    key_id=f"{provider}_key_{idx}"
                )
                self._pools[provider].append(info)
                existing_raw.add(cleaned)
                logger.debug(f"Registered key for {provider}: {info.masked} (ID: {info.key_id})")

    def get_key_count(self, provider: str) -> int:
        return len(self._pools.get(provider.lower(), []))

    def get_available_key(self, provider: str) -> Optional[KeyInfo]:
        """
        Retrieves the next available key for the given provider using round-robin.
        Returns None if all keys are unavailable (in cooldown, exhausted, or invalid).
        """
        provider = provider.lower()
        pool = self._pools.get(provider, [])
        if not pool:
            return None

        # Check for expired cooldowns first
        for key_info in pool:
            _ = key_info.is_available

        available_keys = [k for k in pool if k.is_available]
        if not available_keys:
            return None

        # Round-robin selection among available keys
        current_idx = self._rotation_index.get(provider, 0)
        selected = available_keys[current_idx % len(available_keys)]
        self._rotation_index[provider] = (current_idx + 1) % len(available_keys)
        return selected

    def mark_rate_limited(
        self,
        provider: str,
        key: str,
        retry_after: Optional[float] = None,
        reason: Optional[str] = None
    ) -> None:
        """Mark a key as temporarily rate-limited (HTTP 429)."""
        info = self._find_key_info(provider, key)
        if not info:
            return

        cooldown_sec = retry_after if (retry_after and retry_after > 0) else self.default_cooldown
        info.status = KeyStatus.COOLDOWN
        info.cooldown_until = time.time() + cooldown_sec
        info.failure_count += 1
        info.last_error = reason or "HTTP 429 Rate Limit"
        logger.warning(
            f"[{provider}] Key {info.masked} rate-limited. Placed in COOLDOWN for {cooldown_sec:.1f}s. Error: {info.last_error}"
        )

    def mark_quota_exhausted(self, provider: str, key: str, reason: Optional[str] = None) -> None:
        """Mark a key as exhausted (quota depleted)."""
        info = self._find_key_info(provider, key)
        if not info:
            return

        info.status = KeyStatus.EXHAUSTED
        info.failure_count += 1
        info.last_error = reason or "Quota Exhausted"
        logger.warning(
            f"[{provider}] Key {info.masked} quota exhausted. Marked EXHAUSTED. Error: {info.last_error}"
        )

    def mark_invalid(self, provider: str, key: str, reason: Optional[str] = None) -> None:
        """Mark a key as invalid/unauthorized (HTTP 401/403)."""
        info = self._find_key_info(provider, key)
        if not info:
            return

        info.status = KeyStatus.INVALID
        info.failure_count += 1
        info.last_error = reason or "Invalid Authentication Key"
        logger.error(
            f"[{provider}] Key {info.masked} rejected as INVALID. Reason: {info.last_error}"
        )

    def mark_success(self, provider: str, key: str) -> None:
        """Record a successful response with this key."""
        info = self._find_key_info(provider, key)
        if not info:
            return

        info.success_count += 1
        info.status = KeyStatus.ACTIVE
        info.last_error = None

    def get_provider_status(self, provider: str) -> Dict[str, Any]:
        """Provides status summary of keys for diagnostics and UI telemetry."""
        pool = self._pools.get(provider.lower(), [])
        return {
            "total_keys": len(pool),
            "available_keys": sum(1 for k in pool if k.is_available),
            "keys": [
                {
                    "key_id": k.key_id,
                    "masked": k.masked,
                    "status": k.status.value,
                    "cooldown_remaining": max(0.0, k.cooldown_until - time.time()) if k.status == KeyStatus.COOLDOWN else 0.0,
                    "success_count": k.success_count,
                    "failure_count": k.failure_count,
                    "last_error": k.last_error
                }
                for k in pool
            ]
        }

    def _find_key_info(self, provider: str, raw_key: str) -> Optional[KeyInfo]:
        pool = self._pools.get(provider.lower(), [])
        for k in pool:
            if k.key == raw_key:
                return k
        return None
