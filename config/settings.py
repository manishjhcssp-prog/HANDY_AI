"""
JARVIS AI - Configuration & Secret Settings Loader
Loads environment variables and YAML settings securely.
Supports multiple API keys per provider without exposing secrets in logs or UI.
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml
from dotenv import load_dotenv

# Base directory for the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if present
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()


def mask_key(key: Optional[str]) -> str:
    """Safely mask an API key for logging and UI display.
    Example: 'sk-or-v1-abcdef1234567890' -> 'sk-or...7890'
    """
    if not key or not isinstance(key, str):
        return "none"
    clean = key.strip()
    if len(clean) <= 8:
        return "********"
    prefix = clean[:5]
    suffix = clean[-4:]
    return f"{prefix}...{suffix}"


class Settings:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or (BASE_DIR / "config" / "config.yaml")
        self.raw_config: Dict[str, Any] = self._load_yaml()
        self.free_only_mode: bool = self._get_free_only_mode()
        self.provider_priority: List[str] = self.raw_config.get(
            "provider_priority", ["openrouter", "groq", "gemini", "ollama", "sarvam"]
        )
        self.providers_config: Dict[str, Any] = self._load_providers_config()
        self.router_settings: Dict[str, Any] = self.raw_config.get("router_settings", {})
        self.audio_config: Dict[str, Any] = self.raw_config.get("audio", {})
        self.api_keys: Dict[str, List[str]] = self._load_all_provider_keys()

    def _load_providers_config(self) -> Dict[str, Any]:
        """Loads provider settings and applies environment variable overrides for default models."""
        providers = dict(self.raw_config.get("providers", {}))
        for p_name in ["openrouter", "groq", "gemini", "ollama", "sarvam"]:
            p_dict = dict(providers.get(p_name, {}))
            prefix = p_name.upper()
            env_model = os.getenv(f"{prefix}_DEFAULT_MODEL")
            # Support fallback for legacy or typo env var GEMINI_LDEFAULT_MODE
            if not env_model and p_name == "gemini":
                env_model = os.getenv("GEMINI_LDEFAULT_MODE")
            if env_model and env_model.strip():
                p_dict["default_model"] = env_model.strip()
            providers[p_name] = p_dict
        return providers

    def _load_yaml(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return {}
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _get_free_only_mode(self) -> bool:
        env_val = os.getenv("JARVIS_FREE_ONLY_MODE")
        if env_val is not None:
            return env_val.strip().lower() in ("true", "1", "yes")
        return bool(self.raw_config.get("system", {}).get("free_only_mode", True))

    def _load_all_provider_keys(self) -> Dict[str, List[str]]:
        """
        Discovers all configured keys per provider from environment variables.
        Supports both:
          - PROVIDER_API_KEY
          - PROVIDER_API_KEY_1, PROVIDER_API_KEY_2, etc.
        """
        provider_names = ["openrouter", "groq", "gemini", "ollama", "sarvam"]
        keys_map: Dict[str, List[str]] = {p: [] for p in provider_names}

        for provider in provider_names:
            prefix = provider.upper()
            found_keys: List[str] = []

            # Check single key fallback (e.g. OPENROUTER_API_KEY)
            single_key = os.getenv(f"{prefix}_API_KEY")
            if single_key and single_key.strip():
                found_keys.append(single_key.strip())

            # Additional fallback for Gemini (GOOGLE_API_KEY)
            if provider == "gemini":
                google_key = os.getenv("GOOGLE_API_KEY")
                if google_key and google_key.strip() and google_key.strip() not in found_keys:
                    found_keys.append(google_key.strip())

            # Check numbered keys (e.g. OPENROUTER_API_KEY_1, OPENROUTER_API_KEY_2, ...)
            index = 1
            while True:
                numbered_key = os.getenv(f"{prefix}_API_KEY_{index}")
                if numbered_key and numbered_key.strip():
                    if numbered_key.strip() not in found_keys:
                        found_keys.append(numbered_key.strip())
                    index += 1
                else:
                    # Allow a gap of 1 in numbering, stop if 2 consecutive gaps
                    next_check = os.getenv(f"{prefix}_API_KEY_{index+1}")
                    if next_check and next_check.strip():
                        index += 1
                        continue
                    break

            keys_map[provider] = found_keys

        return keys_map

    def get_api_key(self, provider: str) -> Optional[str]:
        """Returns the first available API key for the given provider, if configured."""
        keys = self.api_keys.get(provider.lower(), [])
        return keys[0] if keys else None

    def get_masked_keys_summary(self) -> Dict[str, List[str]]:
        """Returns masked key representations for UI and safe diagnostic display."""
        summary: Dict[str, List[str]] = {}
        for provider, keys in self.api_keys.items():
            summary[provider] = [mask_key(k) for k in keys]
        return summary


# Global singleton settings instance
settings = Settings()
