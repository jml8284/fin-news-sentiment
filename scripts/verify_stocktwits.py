#!/usr/bin/env python3
"""Diagnose Stocktwits API access from your machine (run outside Cursor sandbox)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.collect_stocktwits import (  # noqa: E402
    BROWSER_HEADERS,
    STOCKTWITS_STREAM_URL,
    _fetch_url,
    _get_access_token,
    fetch_stocktwits_messages_with_error,
    stocktwits_transport_label,
)


def main() -> int:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    url = STOCKTWITS_STREAM_URL.format(symbol=symbol.upper())
    token = _get_access_token()
    if token:
        url = f"{url}?access_token={token[:8]}…"  # display only
        full_url = STOCKTWITS_STREAM_URL.format(symbol=symbol.upper()) + f"?access_token={token}"
    else:
        full_url = STOCKTWITS_STREAM_URL.format(symbol=symbol.upper())

    print("Stocktwits connectivity check")
    print("=" * 50)
    print(f"Symbol: {symbol.upper()}")
    print(f"Token:  {'set (STOCKTWITS_ACCESS_TOKEN)' if token else 'not set'}")
    print(f"Client: {stocktwits_transport_label()}")
    print(f"URL:    {url}")
    print()

    status, text, ctype = _fetch_url(full_url, timeout=20)
    print(f"Raw HTTP status: {status or 'N/A'}")
    print(f"Content-Type:    {ctype or 'N/A'}")
    preview = (text or "")[:200].replace("\n", " ")
    print(f"Body preview:    {preview!r}")
    print()

    if status == 200 and text.strip().startswith("{"):
        try:
            payload = json.loads(text)
            n = len(payload.get("messages") or [])
            print(f"OK — JSON with {n} messages")
        except json.JSONDecodeError:
            print("WARN — status 200 but body is not valid JSON")
    elif status == 403:
        print("BLOCKED — 403 Forbidden")
        print("  Likely causes:")
        print("  • Stocktwits requires Partner-Level Access for streams/symbol")
        print("  • ISP/campus firewall or WAF blocking api.stocktwits.com")
        print("  • Try VPN, different Wi‑Fi, or request partner API access:")
        print("    https://api.stocktwits.com/developers/contact")
    elif stripped := text.strip():
        if stripped.startswith("<!"):
            print("BLOCKED — HTML page instead of JSON (network/WAF)")
        else:
            print("Unexpected response — see preview above")
    else:
        print("FAILED — no response (DNS, proxy, or offline)")

    print()
    df, err = fetch_stocktwits_messages_with_error(symbol)
    print(f"fetch_stocktwits_messages_with_error: rows={len(df)}, error={err!r}")
    if len(df):
        print(f"source: {df.iloc[0].get('source', 'Stocktwits')}")
        if "sample" in str(df.iloc[0].get("source", "")).lower():
            print("NOTE: Using bundled sample data (live API/web blocked on this network).")
    return 0 if len(df) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
