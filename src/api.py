"""Small API entrypoint for live sentiment/chart access.

Run from the repo root:
  uvicorn src.api:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Literal

import pandas as pd
from fastapi import FastAPI, Header, HTTPException, Query

from src.collect_stocktwits import (
    fetch_stocktwits_chart_data,
    fetch_stocktwits_realtime_quotes,
    fetch_stocktwits_sentiment_detail,
)
from src.collect_tradingview import collect_tradingview_screener

API_TOKEN = os.getenv("FIN_NEWS_API_TOKEN", "").strip()

FEATURE_COVERAGE = [
    {"item": "Finviz news screener", "status": "done", "details": "Live Finviz screener/news, ranking, filters, and chart view."},
    {"item": "TradingView numeric screener", "status": "done", "details": "Public TradingView scanner endpoint is available as a secondary numeric screener source."},
    {"item": "Public RSS/newswire sources", "status": "done", "details": "GlobeNewswire, PR Newswire, SEC, FDA, and custom RSS feeds are supported in the news collector."},
    {"item": "Stocktwits social sourcing", "status": "done", "details": "Stocktwits chart, sentiment/detail data when available, parsed messages, and WebSocket quote checks."},
    {"item": "Rolling window", "status": "done", "details": "Stocktwits chart ranges plus optional Finviz K-line rolling window."},
    {"item": "Alerts", "status": "done", "details": "Realtime, chart-window, and social-latest alert rules."},
    {"item": "Correlation", "status": "done", "details": "Quick correlation checks between price, stock volume, sentiment, and message volume."},
    {"item": "Keyword dictionary selections", "status": "done", "details": "Catalyst, risk, squeeze, and long-term keyword buckets."},
    {"item": "Numeric and AI-style ranking", "status": "prototype", "details": "Combined score from numeric screener, sentiment, news activity, and keyword signals."},
    {"item": "Short squeeze and long-term scans", "status": "prototype", "details": "Signal proxies for demo and analyst review, not trading recommendations."},
    {"item": "Project API with token", "status": "done", "details": "FastAPI wrapper exposes health, feature coverage, alert rules, Stocktwits snapshots, and demo reports."},
    {"item": "MongoDB resting database", "status": "prototype", "details": "Optional Mongo module exists; final Streamlit path does not require MongoDB."},
    {"item": "Licensed newswire feeds", "status": "future", "details": "Business Wire, ACCESSWIRE, Benzinga, Dow Jones, and MT Newswires need stable licensed endpoints for production use."},
    {"item": "Redis/Kafka RAM pipeline", "status": "future", "details": "Future production infrastructure for high-throughput message routing."},
    {"item": "Broker trading and bracket orders", "status": "future", "details": "Requires real broker credentials, permissions, and safety controls."},
]

DEFAULT_ALERT_RULES = {
    "realtime_move_threshold_pct": 5.0,
    "chart_window_move_threshold_pct": 7.5,
    "volume_spike_multiple": 2.0,
    "message_volume_threshold": 85.0,
    "bullish_sentiment_threshold": 75.0,
    "bearish_sentiment_threshold": 25.0,
}

app = FastAPI(
    title="Financial News Sentiment API",
    version="0.1.0",
    description="Lightweight API wrapper for live Stocktwits chart, sentiment, and realtime quote checks.",
)


def _check_token(x_api_token: str | None) -> None:
    if API_TOKEN and x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing API token.")


def _latest_row(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {}
    clean = frame.copy()
    if "datetime" in clean.columns:
        clean["datetime"] = pd.to_datetime(clean["datetime"], errors="coerce", utc=True)
        clean = clean.dropna(subset=["datetime"]).sort_values("datetime")
    if clean.empty:
        return {}
    return clean.tail(1).replace({pd.NA: None}).to_dict(orient="records")[0]


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/features")
def feature_coverage(x_api_token: str | None = Header(default=None)) -> dict:
    """Return the professor-checklist coverage in API form."""
    _check_token(x_api_token)
    counts = {
        "done": sum(1 for row in FEATURE_COVERAGE if row["status"] == "done"),
        "prototype": sum(1 for row in FEATURE_COVERAGE if row["status"] == "prototype"),
        "future": sum(1 for row in FEATURE_COVERAGE if row["status"] == "future"),
    }
    return {
        "project": "Financial News Sentiment Dashboard",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "features": FEATURE_COVERAGE,
    }


@app.get("/alerts/rules")
def alert_rules(x_api_token: str | None = Header(default=None)) -> dict:
    """Expose the dashboard alert rules for demo and external integration."""
    _check_token(x_api_token)
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "rules": DEFAULT_ALERT_RULES,
        "types": [
            "Realtime Alert: price movement after the app starts listening.",
            "Chart Window Alert: recent chart-window price and volume movement.",
            "Social Latest Alert: latest Stocktwits sentiment and message-volume scores.",
        ],
    }


@app.get("/tradingview/screener")
def tradingview_screener(
    top_n: int = Query(20, ge=1, le=100),
    min_volume: int = Query(100_000, ge=0),
    sort_by: str = Query("change"),
    sort_order: Literal["asc", "desc"] = Query("desc"),
    x_api_token: str | None = Header(default=None),
) -> dict:
    """Return live TradingView numeric screener rows."""
    _check_token(x_api_token)
    frame = collect_tradingview_screener(
        top_n=top_n,
        min_volume=min_volume,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return {
        "source": "TradingView public scanner",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "rows": int(len(frame)),
        "data": frame.replace({pd.NA: None}).to_dict(orient="records"),
    }


@app.get("/stocktwits/{ticker}")
def stocktwits_snapshot(
    ticker: str,
    zoom: Literal["1d", "1w", "1m", "3m", "6m", "ytd", "1y", "5y", "all"] = Query("1d"),
    include_realtime: bool = Query(True),
    x_api_token: str | None = Header(default=None),
) -> dict:
    _check_token(x_api_token)
    symbol = ticker.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Ticker is required.")

    chart, chart_error = fetch_stocktwits_chart_data(symbol, zoom=zoom)
    detail, detail_error = fetch_stocktwits_sentiment_detail(symbol)

    realtime = pd.DataFrame()
    realtime_error = None
    if include_realtime:
        realtime, realtime_error = fetch_stocktwits_realtime_quotes(symbol, duration_seconds=6.0)

    return {
        "ticker": symbol,
        "zoom": zoom,
        "source": "Stocktwits chart API plus optional Stocktwits WebSocket quote stream",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "chart_rows": int(len(chart)),
        "chart_latest": _latest_row(chart),
        "chart_error": chart_error,
        "realtime_rows": int(len(realtime)),
        "realtime_latest": _latest_row(realtime),
        "realtime_error": realtime_error,
        "sentiment_detail": detail,
        "sentiment_error": detail_error,
    }


@app.get("/stocktwits/{ticker}/demo-report")
def stocktwits_demo_report(
    ticker: str,
    zoom: Literal["1d", "1w", "1m", "3m", "6m", "ytd", "1y", "5y", "all"] = Query("1d"),
    x_api_token: str | None = Header(default=None),
) -> dict:
    """Generate a compact, API-readable report for the current demo ticker."""
    _check_token(x_api_token)
    symbol = ticker.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Ticker is required.")

    chart, chart_error = fetch_stocktwits_chart_data(symbol, zoom=zoom)
    detail, detail_error = fetch_stocktwits_sentiment_detail(symbol)
    latest = _latest_row(chart)

    sentiment_score = None
    message_volume_score = None
    if isinstance(detail, dict):
        sentiment_score = detail.get("sentiment") or detail.get("sentiment_normalized")
        message_volume_score = detail.get("message_volume") or detail.get("message_volume_normalized")

    summary_lines = [
        f"{symbol} Stocktwits demo report",
        f"Chart range: {zoom}",
        f"Chart rows: {len(chart)}",
        f"Latest chart row: {latest.get('datetime', 'N/A') if latest else 'N/A'}",
        f"Latest price: {latest.get('close', latest.get('price', 'N/A')) if latest else 'N/A'}",
        f"Sentiment score: {sentiment_score if sentiment_score is not None else 'N/A'}",
        f"Message-volume score: {message_volume_score if message_volume_score is not None else 'N/A'}",
    ]
    return {
        "ticker": symbol,
        "zoom": zoom,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "chart_rows": int(len(chart)),
        "latest_chart_row": latest,
        "sentiment_score": sentiment_score,
        "message_volume_score": message_volume_score,
        "chart_error": chart_error,
        "sentiment_error": detail_error,
        "summary": "\n".join(summary_lines),
    }
