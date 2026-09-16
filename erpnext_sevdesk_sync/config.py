"""Configuration loading from environment variables."""

from __future__ import annotations

import dataclasses
import os
from typing import Dict, Optional


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


DEFAULT_ERPNEXT_PRICE_LIST = "Standard Selling"
DEFAULT_SEVDESK_BASE_URL = "https://my.sevdesk.de/api/v1"


@dataclasses.dataclass(frozen=True)
class Config:
    erpnext_url: str
    erpnext_api_key: str
    erpnext_api_secret: str
    erpnext_price_list: str
    sevdesk_api_token: str
    sevdesk_base_url: str
    default_tax_rate: Optional[float]
    dry_run: bool

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> "Config":
        env = os.environ if env is None else env

        def require(name: str) -> str:
            value = (env.get(name) or "").strip()
            if not value:
                raise ConfigError(f"Missing required environment variable: {name}")
            return value

        default_tax_rate_raw = (env.get("DEFAULT_TAX_RATE") or "").strip()
        if default_tax_rate_raw:
            try:
                default_tax_rate: Optional[float] = float(default_tax_rate_raw)
            except ValueError as exc:
                raise ConfigError(
                    f"DEFAULT_TAX_RATE must be a number, got {default_tax_rate_raw!r}"
                ) from exc
        else:
            default_tax_rate = None

        price_list = (env.get("ERPNEXT_PRICE_LIST") or "").strip() or DEFAULT_ERPNEXT_PRICE_LIST
        sevdesk_base_url = (env.get("SEVDESK_BASE_URL") or "").strip() or DEFAULT_SEVDESK_BASE_URL

        return cls(
            erpnext_url=require("ERPNEXT_URL").rstrip("/"),
            erpnext_api_key=require("ERPNEXT_API_KEY"),
            erpnext_api_secret=require("ERPNEXT_API_SECRET"),
            erpnext_price_list=price_list,
            sevdesk_api_token=require("SEVDESK_API_TOKEN"),
            sevdesk_base_url=sevdesk_base_url.rstrip("/"),
            default_tax_rate=default_tax_rate,
            dry_run=(env.get("DRY_RUN") or "").strip().lower() in {"1", "true", "yes"},
        )
