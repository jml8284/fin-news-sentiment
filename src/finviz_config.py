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
# override=True: .env wins over stale FINVIZ_API_TOKEN in the shell/IDE.
load_dotenv(PROJECT_ROOT / ".env", override=True)

FINVIZ_ELITE_EXPORT = "https://elite.finviz.com/export"
FINVIZ_ELITE_STOCK = "https://elite.finviz.com/stock"
FINVIZ_ELITE_QUOTE_EXPORT = "https://elite.finviz.com/quote_export"
FINVIZ_ELITE_SCREENER = "https://elite.finviz.com/screener"

# Professor screener (Canvas Jun 10, 2026):
# v=151, rel volume > 0.75, current volume > 100K, technical change up, sort -change.
PRESET_TECHNICAL_GAINERS = {
    "filters": "sh_curvol_o100,sh_relvol_o0.75,ta_change_u",
    "order": "-change",
    "filter_type": "3",
    "view": 151,
    "columns": "0,1,2,6,67,65,66,83,80,30,84,31,85,25,24,63,64,71,72,141,137,136,135",
}


def get_api_token(explicit: str | None = None) -> str:
    """Return Finviz Elite API token from CLI or FINVIZ_API_TOKEN env var."""
    if explicit:
        token = explicit.strip()
    else:
        load_dotenv(PROJECT_ROOT / ".env", override=True)
        token = os.getenv("FINVIZ_API_TOKEN", "").strip()
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
    view: int = 151,
    filter_type: str = "3",
    columns: str | None = None,
    after_row: int | None = None,
) -> str:
    """Build the Elite export CSV URL (screener export + auth)."""
    params: dict[str, str | int] = {
        "v": view,
        "f": filters,
        "ft": filter_type,
        "o": order,
        "auth": auth_token,
    }
    if columns:
        params["c"] = columns
    if after_row is not None:
        params["ar"] = after_row
    return f"{FINVIZ_ELITE_EXPORT}?{urlencode(params)}"


def build_elite_screener_url(
    *,
    filters: str,
    order: str = "-change",
    view: int = 151,
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


def build_elite_stock_url(
    ticker: str,
    auth_token: str | None = None,
    *,
    period: str = "i1",
    chart_type: str = "c",
    bars: str | None = None,
) -> str:
    """
    Build the Elite stock chart page URL for a ticker.

    Professor example: https://elite.finviz.com/stock?t=SCAG&ty=c&p=i1
    """
    params: dict[str, str] = {
        "t": ticker.upper().strip(),
        "ty": chart_type,
        "p": period,
    }
    if bars:
        params["b"] = bars
    if auth_token:
        params["auth"] = auth_token
    return f"{FINVIZ_ELITE_STOCK}?{urlencode(params)}"


def build_quote_export_url(
    ticker: str,
    auth_token: str,
    *,
    period: str = "i1",
    chart_type: str = "c",
) -> str:
    """
    Build the Elite quote_export API URL (professor API workflow).

    Example: https://elite.finviz.com/quote_export?t=SCAG&ty=c&p=i1&auth=TOKEN
    """
    params = {
        "t": ticker.upper().strip(),
        "ty": chart_type,
        "p": period,
        "auth": auth_token,
    }
    return f"{FINVIZ_ELITE_QUOTE_EXPORT}?{urlencode(params)}"
