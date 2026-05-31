"""
Shared Finviz Elite URLs, presets, and API token loading.

Set your personal token in a local .env file (never commit it):
  FINVIZ_API_TOKEN=your-token-here
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlencode

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

FINVIZ_ELITE_EXPORT = "https://elite.finviz.com/export"
FINVIZ_ELITE_STOCK = "https://elite.finviz.com/stock"
FINVIZ_ELITE_SCREENER = "https://elite.finviz.com/screener"

# Professor screener: Technical tab, change up, high current volume & relative volume.
PRESET_TECHNICAL_GAINERS = {
    "filters": "sh_curvol_o100,sh_relvol_o10,ta_change_u",
    "order": "-change",
    "filter_type": "3",
    "view": 111,
}


def get_api_token(explicit: str | None = None) -> str:
    """Return Finviz Elite API token from CLI or FINVIZ_API_TOKEN env var."""
    token = (explicit or os.getenv("FINVIZ_API_TOKEN", "")).strip()
    if not token:
        raise RuntimeError(
            "Finviz Elite API token required. "
            "Create .env with FINVIZ_API_TOKEN=... (see .env.example) "
            "or pass --auth-token."
        )
    return token


def build_elite_export_url(
    *,
    auth_token: str,
    filters: str,
    order: str = "-change",
    view: int = 111,
    filter_type: str = "3",
) -> str:
    """Build the Elite export CSV URL (screener export + auth)."""
    params = {
        "v": view,
        "f": filters,
        "ft": filter_type,
        "o": order,
        "auth": auth_token,
    }
    return f"{FINVIZ_ELITE_EXPORT}?{urlencode(params)}"


def build_elite_screener_url(
    *,
    filters: str,
    order: str = "-change",
    view: int = 111,
    filter_type: str = "3",
) -> str:
    """Build the Elite screener page URL (no auth in URL)."""
    params = {
        "v": view,
        "f": filters,
        "ft": filter_type,
        "o": order,
    }
    return f"{FINVIZ_ELITE_SCREENER}?{urlencode(params)}"


def build_elite_stock_url(ticker: str, auth_token: str | None = None) -> str:
    """
    Build the Elite stock chart page URL for a ticker.

    Example: https://elite.finviz.com/stock?t=DEVS&ty=c&p=d&b=1
    """
    params: dict[str, str] = {
        "t": ticker.upper().strip(),
        "ty": "c",
        "p": "d",
        "b": "1",
    }
    if auth_token:
        params["auth"] = auth_token
    return f"{FINVIZ_ELITE_STOCK}?{urlencode(params)}"
