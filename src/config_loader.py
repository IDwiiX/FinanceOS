# src/config_loader.py
"""Loads settings.yaml + .env. Infrastructure only — no business logic."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SETTINGS_PATH = _PROJECT_ROOT / "config" / "settings.yaml"
_ENV_PATH = _PROJECT_ROOT / "config" / ".env"


def load_config() -> dict[str, Any]:
    """Read settings.yaml into a dict and load .env into os.environ."""
    load_dotenv(_ENV_PATH)
    with _SETTINGS_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get_secret(key: str, default: str | None = None) -> str | None:
    """Fetch a value from environment (populated by .env)."""
    return os.getenv(key, default)
