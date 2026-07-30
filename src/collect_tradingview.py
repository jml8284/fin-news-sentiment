"""TradingView numeric screener collector.

This module uses TradingView's public scanner endpoint for numeric market data.
It does not require a TradingView login for the basic screener fields used here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = PROJECT_ROOT / "data" / "raw" / "tradingview_screener.csv"
TRADINGVIEW_SCAN_URL = "https://scanner.tradingview.com/america/scan"

TRADINGVIEW_COLUMNS = [
    "name",
    "description",
    "close",
    "change",
    "volume",
    "market_cap_basic",
    "premarket_change",
    "postmarket_change",
    "relative_volume_10d_calc",
    "sector",
    "industry",
    "exchange",
]


def build_tradingview_payload(
    *,
    top_n: int = 20,
    min_volume: int = 100_000,
    sort_by: str = "change",
    sort_order: str = "desc",
) -> dict[str, Any]:
    """Build the TradingView scanner request payload."""
    top_n = max(1, int(top_n))
    min_volume = max(0, int(min_volume))
    return {
        "filter": [
            {"left": "type", "operation": "equal", "right": "stock"},
            {"left": "volume", "operation": "greater", "right": min_volume},
        ],
        "options": {"lang": "en"},
        "markets": ["america"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": TRADINGVIEW_COLUMNS,
        "sort": {"sortBy": sort_by, "sortOrder": sort_order},
        "range": [0, top_n],
    }


def fetch_tradingview_scan(
    *,
    top_n: int = 20,
    min_volume: int = 100_000,
    sort_by: str = "change",
    sort_order: str = "desc",
    timeout: int = 25,
) -> dict[str, Any]:
    payload = build_tradingview_payload(
        top_n=top_n,
        min_volume=min_volume,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    response = requests.post(
        TRADINGVIEW_SCAN_URL,
        json=payload,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def normalize_tradingview_rows(raw: dict[str, Any]) -> pd.DataFrame:
    rows = raw.get("data") or []
    records: list[dict[str, Any]] = []
    fetched_at = datetime.now(timezone.utc).isoformat()
    for idx, row in enumerate(rows, start=1):
        values = row.get("d") or []
        item = dict(zip(TRADINGVIEW_COLUMNS, values, strict=False))
        ticker = str(item.get("name") or "").upper().strip()
        exchange = str(item.get("exchange") or str(row.get("s") or "").split(":")[0]).upper().strip()
        if not ticker:
            continue
        records.append(
            {
                "screener_rank": idx,
                "ticker": ticker,
                "company": item.get("description"),
                "exchange": exchange,
                "price": item.get("close"),
                "change_pct": item.get("change"),
                "volume": item.get("volume"),
                "market_cap": item.get("market_cap_basic"),
                "premarket_change_pct": item.get("premarket_change"),
                "postmarket_change_pct": item.get("postmarket_change"),
                "relative_volume_10d": item.get("relative_volume_10d_calc"),
                "sector": item.get("sector"),
                "industry": item.get("industry"),
                "source": "TradingView",
                "source_url": f"https://www.tradingview.com/symbols/{exchange}-{ticker}/",
                "fetched_at": fetched_at,
            }
        )
    return pd.DataFrame.from_records(records)


def collect_tradingview_screener(
    *,
    top_n: int = 20,
    min_volume: int = 100_000,
    sort_by: str = "change",
    sort_order: str = "desc",
) -> pd.DataFrame:
    raw = fetch_tradingview_scan(
        top_n=top_n,
        min_volume=min_volume,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return normalize_tradingview_rows(raw)


def save_tradingview_screener(frame: pd.DataFrame, out_path: Path = DEFAULT_OUT) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out_path, index=False)
    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect TradingView numeric screener rows.")
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--min-volume", type=int, default=100_000)
    parser.add_argument("--sort-by", default="change")
    parser.add_argument("--sort-order", choices=["asc", "desc"], default="desc")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = collect_tradingview_screener(
        top_n=args.top_n,
        min_volume=args.min_volume,
        sort_by=args.sort_by,
        sort_order=args.sort_order,
    )
    out_path = save_tradingview_screener(frame, args.out)
    print(f"Saved {len(frame)} TradingView rows to {out_path}")


if __name__ == "__main__":
    main()
