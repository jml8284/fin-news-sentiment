"""Live social metrics for the Streamlit dashboard.

This module replaces the dashboard's Stocktwits dependency with a broader
social source abstraction. The current live source is Bluesky.
"""
from __future__ import annotations

import os
from datetime import date

import pandas as pd

from src.collect_social import SOCIAL_COLUMNS, fetch_social_posts_with_error
from src.news_filters import in_date_range, utc_today
from src.ticker_ranking import density_bucket


def _live_ticker_limit() -> int:
    try:
        return max(int(os.getenv("SOCIAL_LIVE_TICKER_LIMIT", "5")), 0)
    except ValueError:
        return 5


def _request_timeout() -> int:
    try:
        return max(int(os.getenv("SOCIAL_TIMEOUT_SEC", "4")), 1)
    except ValueError:
        return 4


def _max_subreddits() -> int:
    try:
        return max(int(os.getenv("SOCIAL_REDDIT_MAX_SUBREDDITS", "1")), 1)
    except ValueError:
        return 1


def _empty_messages() -> pd.DataFrame:
    return pd.DataFrame(columns=SOCIAL_COLUMNS)


def filter_social_by_date(
    messages: pd.DataFrame,
    *,
    window_start: date | None,
    window_end: date | None,
) -> pd.DataFrame:
    if messages.empty or "ticker" not in messages.columns:
        return _empty_messages()
    if window_start is None and window_end is None:
        return messages.copy()
    start = window_start or date(2000, 1, 1)
    end = window_end or utc_today()
    if start > end:
        start, end = end, start
    mask = messages["published"].map(lambda p: in_date_range(p, start=start, end=end))
    return messages[mask].copy()


def fetch_live_social(tickers: list[str]) -> tuple[pd.DataFrame, list[str]]:
    unique: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = str(raw).upper().strip()
        if ticker and ticker not in seen:
            seen.add(ticker)
            unique.append(ticker)

    if not unique:
        return _empty_messages(), []

    live_limit = _live_ticker_limit()
    frames: list[pd.DataFrame] = []
    errors: list[str] = []

    for idx, ticker in enumerate(unique):
        if live_limit > 0 and idx >= live_limit:
            continue
        df, err = fetch_social_posts_with_error(
            ticker,
            max_items=30,
            timeout=_request_timeout(),
            max_subreddits=_max_subreddits(),
        )
        if err and "no " not in err.lower():
            errors.append(f"{ticker}: {err}")
        if not df.empty:
            frames.append(df)

    if not frames:
        return _empty_messages(), errors
    return pd.concat(frames, ignore_index=True), errors


def build_social_metrics(
    messages: pd.DataFrame,
    tickers: list[str],
    *,
    window_start: date | None = None,
    window_end: date | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    unique: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = str(raw).upper().strip()
        if ticker and ticker not in seen:
            seen.add(ticker)
            unique.append(ticker)

    if not unique:
        empty = pd.DataFrame(columns=["ticker", "social_count", "social_density"])
        return empty, _empty_messages()

    filtered = filter_social_by_date(
        messages,
        window_start=window_start,
        window_end=window_end,
    )

    records: list[dict[str, object]] = []
    for ticker in unique:
        if filtered.empty or "ticker" not in filtered.columns:
            count = 0
        else:
            sub = filtered[filtered["ticker"].astype(str).str.upper() == ticker]
            count = int(len(sub))
        records.append(
            {
                "ticker": ticker,
                "social_count": count,
                "social_density": density_bucket(count),
            }
        )

    return pd.DataFrame.from_records(records), filtered
