#!/usr/bin/env python3
"""Verify live Finviz screener + quote-page news scraping (run from repo root)."""
from __future__ import annotations

from src.collect_news import fetch_finviz_news
from src.collect_stocks import collect_finviz_elite_export
from src.finviz_config import PRESET_TECHNICAL_GAINERS, get_api_token
from src.live_finviz_metrics import build_live_finviz_metrics


def main() -> None:
    token = get_api_token()
    print("Token prefix:", token[:4])

    screener = collect_finviz_elite_export(
        auth_token=token,
        filters=PRESET_TECHNICAL_GAINERS["filters"],
        order=PRESET_TECHNICAL_GAINERS["order"],
        filter_type=str(PRESET_TECHNICAL_GAINERS["filter_type"]),
        view=int(PRESET_TECHNICAL_GAINERS["view"]),
        columns=PRESET_TECHNICAL_GAINERS.get("columns"),
        top_n=20,
    )
    tickers = screener["ticker"].astype(str).str.upper().tolist()
    print(f"Screener OK: {len(tickers)} tickers -> {tickers[:5]}...")

    sample = tickers[0]
    sample_news = fetch_finviz_news(sample, max_items=0, auth_token=token)
    print(f"Sample live news ({sample}): {len(sample_news)} rows")
    if not sample_news.empty:
        print(" ", sample_news.iloc[0]["title"][:80])

    metrics, scored, errors = build_live_finviz_metrics(tickers, token)
    total = int(metrics["news_count"].fillna(0).sum())
    with_news = int((metrics["news_count"].fillna(0) > 0).sum())
    print(f"Live metrics: {with_news}/{len(metrics)} tickers with Finviz news, {total} articles total")
    if errors:
        print("Errors (first 3):", errors[:3])
    if total == 0:
        raise SystemExit(
            "FAIL: 0 Finviz news scraped. Check token, network, or Finviz page markup."
        )
    print("PASS: live Finviz data is working.")


if __name__ == "__main__":
    main()
