"""Live Stocktwits metrics for the Streamlit dashboard."""
from __future__ import annotations

import os
from datetime import date

import pandas as pd

from src.collect_stocktwits import (
    MESSAGE_COLUMNS,
    _load_sample_messages,
    fetch_stocktwits_messages_with_error,
)
from src.news_filters import in_date_range, utc_today
from src.ticker_ranking import density_bucket


def _live_ticker_limit() -> int:
    try:
        return max(int(os.getenv("STOCKTWITS_LIVE_TICKER_LIMIT", "5")), 0)
    except ValueError:
        return 5


def _is_rate_block(err: str | None) -> bool:
    if not err:
        return False
    lowered = err.lower()
    return any(token in lowered for token in ("403", "429", "rate limit", "forbidden", "blocked"))


def _fetch_one(ticker: str, *, sample_only: bool) -> tuple[str, pd.DataFrame, str | None]:
    try:
        if sample_only:
            df = _load_sample_messages(ticker, max_items=30)
            if df.empty:
                return ticker.upper(), df, "sample only (rate limit)"
            return ticker.upper(), df, None
        df, err = fetch_stocktwits_messages_with_error(ticker, max_items=30)
        if err and err != "no messages for this symbol":
            return ticker.upper(), df, err
        return ticker.upper(), df, None
    except Exception as exc:  # noqa: BLE001
        return ticker.upper(), pd.DataFrame(columns=MESSAGE_COLUMNS), str(exc)


def _empty_messages() -> pd.DataFrame:
    return pd.DataFrame(columns=MESSAGE_COLUMNS)


def filter_stocktwits_by_date(
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


def fetch_live_stocktwits(tickers: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """Fetch Stocktwits sequentially with rate limits; sample-fill after blocks."""
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
    sample_only = False
    rate_blocks = 0

    for idx, ticker in enumerate(unique):
        use_sample = sample_only or (live_limit > 0 and idx >= live_limit)
        _, df, err = _fetch_one(ticker, sample_only=use_sample)
        if err:
            errors.append(f"{ticker}: {err}")
            if not use_sample and _is_rate_block(err):
                rate_blocks += 1
                if rate_blocks >= 2:
                    sample_only = True
                    errors.append("Stocktwits: switched to sample data after repeated rate blocks")
        if not df.empty:
            frames.append(df)

    if not frames:
        return _empty_messages(), errors
    return pd.concat(frames, ignore_index=True), errors


def build_stocktwits_metrics(
    messages: pd.DataFrame,
    tickers: list[str],
    *,
    window_start: date | None = None,
    window_end: date | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (per-ticker metrics, filtered messages)."""
    unique: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = str(raw).upper().strip()
        if ticker and ticker not in seen:
            seen.add(ticker)
            unique.append(ticker)

    if not unique:
        empty = pd.DataFrame(columns=["ticker", "stocktwits_count", "social_density"])
        return empty, _empty_messages()

    filtered = filter_stocktwits_by_date(
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
                "stocktwits_count": count,
                "social_density": density_bucket(count),
            }
        )

    return pd.DataFrame.from_records(records), filtered
