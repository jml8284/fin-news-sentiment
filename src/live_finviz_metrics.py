"""
Live Finviz quote-page news metrics for the Streamlit dashboard.

Fetches news directly from Finviz Elite stock pages (same as the professor's
ground-truth quote view), not from pipeline CSV snapshots.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

import pandas as pd

from src.collect_news import fetch_finviz_news
from src.news_filters import in_date_range, utc_today
from src.sentiment_engines import analyze_dataframe
from src.ticker_ranking import density_bucket


def _fetch_one_ticker(ticker: str, token: str) -> tuple[str, pd.DataFrame, str | None]:
    try:
        df = fetch_finviz_news(ticker, max_items=0, auth_token=token, use_elite=True)
        return ticker.upper(), df, None
    except Exception as exc:  # noqa: BLE001
        return ticker.upper(), pd.DataFrame(), str(exc)


def filter_scored_news_by_date(
    scored: pd.DataFrame,
    *,
    window_start: date | None,
    window_end: date | None,
) -> pd.DataFrame:
    """Keep rows whose published date falls in window (inclusive UTC days)."""
    if scored.empty or (window_start is None and window_end is None):
        return scored
    start = window_start or date(2000, 1, 1)
    end = window_end or utc_today()
    if start > end:
        start, end = end, start
    mask = scored["published"].map(lambda p: in_date_range(p, start=start, end=end))
    return scored[mask].copy()


def build_metrics_from_scored(
    scored: pd.DataFrame,
    tickers: list[str],
    *,
    window_start: date | None = None,
    window_end: date | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Aggregate news_count / message_density / sentiment_rank for each ticker.

    Returns (metrics, filtered_scored) where filtered_scored respects the date window.
    """
    unique = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = str(raw).upper().strip()
        if ticker and ticker not in seen:
            seen.add(ticker)
            unique.append(ticker)

    if not unique:
        empty = pd.DataFrame(columns=["ticker", "news_count", "message_density", "sentiment_rank"])
        return empty, pd.DataFrame()

    filtered = filter_scored_news_by_date(
        scored,
        window_start=window_start,
        window_end=window_end,
    )

    records: list[dict[str, object]] = []
    for ticker in unique:
        sub = filtered[filtered["ticker"].astype(str).str.upper() == ticker]
        count = int(len(sub))
        records.append(
            {
                "ticker": ticker,
                "news_count": count,
                "message_density": density_bucket(count),
            }
        )

    metrics = pd.DataFrame.from_records(records)
    if not filtered.empty:
        avg = (
            filtered.groupby("ticker", as_index=False)["sentiment_compound"]
            .mean()
            .rename(columns={"sentiment_compound": "avg_sentiment"})
        )
        avg["ticker"] = avg["ticker"].astype(str).str.upper()
        metrics = metrics.merge(avg, on="ticker", how="left")
        metrics = metrics.sort_values(
            ["avg_sentiment", "news_count"],
            ascending=[False, False],
            na_position="last",
        ).reset_index(drop=True)
        metrics.insert(0, "sentiment_rank", range(1, len(metrics) + 1))
        metrics = metrics.drop(columns=["avg_sentiment"], errors="ignore")
    else:
        metrics.insert(0, "sentiment_rank", range(1, len(metrics) + 1))

    return metrics, filtered


def fetch_and_score_live_finviz_news(
    tickers: list[str],
    token: str,
    *,
    engine: str = "vader",
    max_workers: int = 6,
) -> tuple[pd.DataFrame, list[str]]:
    """Scrape Finviz quote pages and score every article (no date filter yet)."""
    unique = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = str(raw).upper().strip()
        if ticker and ticker not in seen:
            seen.add(ticker)
            unique.append(ticker)

    if not unique:
        return pd.DataFrame(), []

    news_by_ticker: dict[str, pd.DataFrame] = {}
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_fetch_one_ticker, ticker, token) for ticker in unique]
        for future in as_completed(futures):
            ticker, df, err = future.result()
            if err:
                errors.append(f"{ticker}: {err}")
            news_by_ticker[ticker] = df

    frames = [df for df in news_by_ticker.values() if not df.empty]
    if not frames:
        return pd.DataFrame(), errors

    combined = pd.concat(frames, ignore_index=True)
    return analyze_dataframe(combined, engine=engine), errors


def build_live_finviz_metrics(
    tickers: list[str],
    token: str,
    *,
    engine: str = "vader",
    max_workers: int = 6,
    window_start: date | None = None,
    window_end: date | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """
    Scrape + score + aggregate. Prefer fetch_and_score + build_metrics_from_scored
    in the dashboard so date filters do not re-hit Finviz.
    """
    scored, errors = fetch_and_score_live_finviz_news(
        tickers,
        token,
        engine=engine,
        max_workers=max_workers,
    )
    metrics, filtered = build_metrics_from_scored(
        scored,
        tickers,
        window_start=window_start,
        window_end=window_end,
    )
    return metrics, filtered, errors


def resolve_news_window_preset(
    preset: str,
    *,
    custom_start: date,
    custom_end: date,
) -> tuple[date | None, date | None, str]:
    """Map sidebar preset to inclusive UTC date window."""
    today = utc_today()
    if preset == "All on page":
        return None, None, "all articles on Finviz quote page"
    if preset == "Last 7 days":
        start = today - timedelta(days=6)
        return start, today, f"{start} → {today}"
    if preset == "Last 30 days":
        start = today - timedelta(days=29)
        return start, today, f"{start} → {today}"
    if preset == "Last 6 months":
        start = today - timedelta(days=182)
        return start, today, f"{start} → {today}"
    if preset == "Custom":
        start, end = custom_start, custom_end
        if start > end:
            start, end = end, start
        return start, end, f"{start} → {end}"
    start = today - timedelta(days=6)
    return start, today, f"{start} → {today}"
