"""
Streamlit dashboard: Finviz live chart + screener table + news viewer.

Ranked tickers and news_count come from **live Finviz quote pages** (60s refresh),
not pipeline CSV snapshots.

Social sourcing lives in its own tab + sidebar section - does not alter Finviz.

Run from repo root:
  streamlit run src/dashboard.py
"""
from __future__ import annotations

import calendar
import sys
import re
from datetime import datetime, time as datetime_time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.finviz_charts import (
    PERIOD_OPTIONS,
    available_sma_periods,
    build_finviz_style_chart,
    default_sma_periods,
    fetch_quote_bars,
    filter_bars_by_date_window,
    latest_price_info,
    window_change_pct,
)
from src.collect_stocks import collect_finviz_elite_export
from src.collect_tradingview import collect_tradingview_screener
from src.finviz_config import (
    PRESET_TECHNICAL_GAINERS,
    build_elite_stock_url,
    get_api_token,
)
from src.collect_stocktwits import (
    fetch_stocktwits_chart_data,
    fetch_stocktwits_realtime_quotes,
    fetch_stocktwits_sentiment_detail,
)
from src.live_finviz_metrics import (
    build_metrics_from_scored,
    fetch_and_score_live_finviz_news,
    resolve_news_window_preset,
)
from src.live_social_metrics import build_social_metrics, fetch_live_social
from src.news_filters import utc_today
from src.sentiment_engines import analyze_dataframe, read_engine_metadata

ENGINE_META = PROJECT_ROOT / "data" / "processed" / "sentiment_engine.txt"
LIVE_SCORE_ENGINE = "vader"
DISPLAY_TZ = ZoneInfo("America/New_York")
DISPLAY_TZ_LABEL = "ET"
PROFESSOR_TEST_TICKERS = ["ZCMD", "ZYBT", "BIYA", "STAK", "SDOT", "PHOE", "LEDS", "CJMB"]
KEYWORD_GROUPS = {
    "Catalyst": [
        "approval",
        "approved",
        "breakthrough",
        "contract",
        "deal",
        "fda",
        "guidance",
        "launch",
        "partnership",
        "patent",
        "phase",
        "positive",
        "raises",
        "record",
    ],
    "Risk": [
        "bankruptcy",
        "delay",
        "downgrade",
        "investigation",
        "lawsuit",
        "loss",
        "offering",
        "probe",
        "recall",
        "risk",
        "sec",
        "short",
        "warn",
    ],
    "Gossip": [
        "buyout",
        "guaranteed",
        "heard",
        "insider",
        "leak",
        "moon",
        "pump",
        "rumor",
        "trust me",
        "unconfirmed",
        "whisper",
    ],
    "Squeeze": [
        "borrow",
        "cover",
        "float",
        "gamma",
        "halt",
        "high short interest",
        "low float",
        "short squeeze",
        "squeeze",
        "unusual volume",
    ],
    "Long-term": [
        "cash flow",
        "dividend",
        "earnings",
        "growth",
        "margin",
        "revenue",
        "strategic",
        "upgrade",
        "valuation",
    ],
}


def _keyword_group_key(group: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", group.lower()).strip("_")


def _to_display_time(values: pd.Series) -> pd.Series:
    dt = pd.to_datetime(values, errors="coerce", utc=True)
    return dt.dt.tz_convert(DISPLAY_TZ).dt.tz_localize(None)


def _format_display_time(value: object) -> str:
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return "N/A"
    return ts.tz_convert(DISPLAY_TZ).strftime(f"%Y-%m-%d %H:%M:%S {DISPLAY_TZ_LABEL}")


def _format_display_range(values: pd.Series) -> str:
    dt = pd.to_datetime(values, errors="coerce", utc=True).dropna()
    if dt.empty:
        return "N/A"
    start = dt.min().tz_convert(DISPLAY_TZ)
    end = dt.max().tz_convert(DISPLAY_TZ)
    if start.date() == end.date():
        return f"{start.strftime('%Y-%m-%d %H:%M')} -> {end.strftime('%H:%M')} {DISPLAY_TZ_LABEL}"
    return f"{start.strftime('%Y-%m-%d %H:%M')} -> {end.strftime('%Y-%m-%d %H:%M')} {DISPLAY_TZ_LABEL}"


def _format_median_interval(values: pd.Series) -> str:
    dt = pd.to_datetime(values, errors="coerce", utc=True).dropna().sort_values()
    if len(dt) < 2:
        return "N/A"
    seconds = dt.diff().dt.total_seconds().dropna()
    if seconds.empty:
        return "N/A"
    median_seconds = float(seconds.median())
    if median_seconds < 3600:
        minutes = max(1, round(median_seconds / 60))
        return f"{minutes} min"
    if median_seconds < 86400:
        hours = median_seconds / 3600
        return f"{hours:.1f} hr" if hours % 1 else f"{int(hours)} hr"
    days = median_seconds / 86400
    return f"{days:.1f} days" if days % 1 else f"{int(days)} days"


def _median_timedelta(values: pd.Series, fallback_minutes: int = 30) -> pd.Timedelta:
    dt = pd.to_datetime(values, errors="coerce", utc=True).dropna().sort_values()
    if len(dt) < 2:
        return pd.Timedelta(minutes=fallback_minutes)
    step = pd.to_timedelta(dt.diff().median())
    if pd.isna(step) or step <= pd.Timedelta(0):
        return pd.Timedelta(minutes=fallback_minutes)
    return step


def _break_large_time_gaps(
    frame: pd.DataFrame,
    *,
    datetime_col: str,
    max_gap: pd.Timedelta,
) -> pd.DataFrame:
    """Insert blank rows so Plotly does not connect separate market sessions."""
    if frame.empty or datetime_col not in frame.columns:
        return frame
    ordered = frame.sort_values(datetime_col).reset_index(drop=True)
    deltas = pd.to_datetime(ordered[datetime_col], errors="coerce", utc=True).diff()
    blanks: list[pd.Series] = []
    for idx, delta in deltas.items():
        if idx > 0 and pd.notna(delta) and delta > max_gap:
            blank = ordered.iloc[idx].copy()
            blank.loc[:] = pd.NA
            blank[datetime_col] = ordered.loc[idx - 1, datetime_col] + pd.Timedelta(seconds=1)
            blanks.append(blank)
    if not blanks:
        return ordered
    return (
        pd.concat([ordered, pd.DataFrame(blanks)], ignore_index=True)
        .sort_values(datetime_col)
        .reset_index(drop=True)
    )


@st.cache_data(ttl=60)
def load_live_bars(ticker: str, period_code: str, token: str) -> pd.DataFrame:
    return fetch_quote_bars(ticker, period=period_code, auth_token=token)


@st.cache_data(ttl=60)
def load_live_screener(token: str) -> pd.DataFrame:
    preset = PRESET_TECHNICAL_GAINERS
    stocks = collect_finviz_elite_export(
        auth_token=token,
        filters=preset["filters"],
        order=preset["order"],
        filter_type=str(preset["filter_type"]),
        view=int(preset["view"]),
        columns=preset.get("columns"),
        top_n=20,
    )
    stocks = stocks.copy()
    stocks["ticker"] = stocks["ticker"].astype(str).str.upper()
    stocks.insert(0, "screener_rank", range(1, len(stocks) + 1))
    return stocks


@st.cache_data(ttl=60, show_spinner="Fetching TradingView screener...")
def load_tradingview_screener(top_n: int, min_volume: int, sort_by: str, sort_order: str) -> pd.DataFrame:
    return collect_tradingview_screener(
        top_n=top_n,
        min_volume=min_volume,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@st.cache_data(ttl=300, show_spinner="Fetching live Finviz news...")
def load_live_finviz_scored(
    tickers: tuple[str, ...],
    token: str,
    engine: str,
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    scored, errors = fetch_and_score_live_finviz_news(list(tickers), token, engine=engine)
    return scored, tuple(errors)


@st.cache_data(ttl=900, show_spinner="Fetching social posts (rate-limited, cached 15 min)...")
def load_live_social(tickers: tuple[str, ...]) -> tuple[pd.DataFrame, tuple[str, ...]]:
    messages, errors = fetch_live_social(list(tickers))
    return messages, tuple(errors)


@st.cache_data(ttl=120, show_spinner="Fetching Stocktwits sentiment gateway data...")
def load_stocktwits_sentiment_detail(ticker: str) -> tuple[dict, str | None]:
    return fetch_stocktwits_sentiment_detail(ticker)


@st.cache_data(ttl=60, show_spinner="Fetching Stocktwits chart data...")
def load_stocktwits_chart_data(ticker: str, zoom: str) -> tuple[pd.DataFrame, str | None]:
    return fetch_stocktwits_chart_data(ticker, zoom=zoom)


@st.cache_data(ttl=1, show_spinner="Listening to Stocktwits realtime quote stream...")
def load_stocktwits_realtime_quotes(ticker: str) -> tuple[pd.DataFrame, str | None]:
    return fetch_stocktwits_realtime_quotes(ticker, duration_seconds=10.0)


def merge_live_screener_with_metrics(live: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    out = live
    if not metrics.empty:
        cols = [c for c in ("ticker", "sentiment_rank", "news_count", "message_density") if c in metrics.columns]
        if len(cols) > 1:
            side = metrics[cols].copy()
            side["ticker"] = side["ticker"].astype(str).str.upper()
            out = out.merge(side, on="ticker", how="left")
    return out


def fallback_screener() -> pd.DataFrame:
    tickers = ["AAPL", "TSLA", "NVDA", "AMD", "QQQ", "SPY", "PLTR", "MSTR", "SOFI", "COIN"]
    return pd.DataFrame(
        {
            "screener_rank": range(1, len(tickers) + 1),
            "ticker": tickers,
            "company": tickers,
        }
    )


def filter_table(df: pd.DataFrame, sector: str, min_news: int) -> pd.DataFrame:
    out = df.copy()
    if sector != "All" and "sector" in out.columns:
        out = out[out["sector"].fillna("").astype(str) == sector]
    if min_news > 0 and "news_count" in out.columns:
        out = out[out["news_count"].fillna(0) >= min_news]
    return out


def _numeric_column(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    cleaned = (
        df[column]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace("$", "", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(default)


def _percentile_score(values: pd.Series, *, higher_is_better: bool = True) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.notna().sum() <= 1 or numeric.nunique(dropna=True) <= 1:
        return pd.Series(50.0, index=values.index)
    ranks = numeric.rank(pct=True, ascending=higher_is_better, na_option="bottom")
    return (ranks * 100).fillna(0).clip(0, 100)


def build_keyword_signals(scored: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    unique = list(dict.fromkeys(str(t).upper().strip() for t in tickers if str(t).strip()))
    if scored.empty:
        return pd.DataFrame(
            {
                "ticker": unique,
                "keyword_hits": 0,
                "catalyst_hits": 0,
                "risk_hits": 0,
                "gossip_hits": 0,
                "squeeze_hits": 0,
                "long_term_hits": 0,
                "top_keyword_group": "None",
            }
        )

    work = scored.copy()
    work["ticker"] = work["ticker"].astype(str).str.upper()
    title = work["title"].astype(str) if "title" in work.columns else pd.Series("", index=work.index)
    summary = work["summary"].astype(str) if "summary" in work.columns else pd.Series("", index=work.index)
    work["_keyword_text"] = (title + " " + summary).str.lower()
    for ticker in unique:
        sub = work[work["ticker"] == ticker]
        row: dict[str, object] = {"ticker": ticker}
        total_hits = 0
        group_counts: dict[str, int] = {}
        for group, terms in KEYWORD_GROUPS.items():
            hits = 0
            for term in terms:
                hits += int(sub["_keyword_text"].str.contains(re.escape(term.lower()), na=False).sum())
            key = _keyword_group_key(group) + "_hits"
            row[key] = hits
            group_counts[group] = hits
            total_hits += hits
        row["keyword_hits"] = total_hits
        row["top_keyword_group"] = max(group_counts, key=group_counts.get) if total_hits else "None"
        records.append(row)
    return pd.DataFrame.from_records(records)


def build_signal_dashboard_table(
    filtered: pd.DataFrame,
    scored: pd.DataFrame,
    tickers: list[str],
) -> pd.DataFrame:
    if filtered.empty:
        return filtered.copy()

    out = filtered.copy()
    out["ticker"] = out["ticker"].astype(str).str.upper()
    keywords = build_keyword_signals(scored, tickers)
    out = out.merge(keywords, on="ticker", how="left")

    change = _numeric_column(out, "change_pct")
    volume = _numeric_column(out, "volume")
    news_count = _numeric_column(out, "news_count")
    price = _numeric_column(out, "price")
    keyword_hits = _numeric_column(out, "keyword_hits")
    catalyst_hits = _numeric_column(out, "catalyst_hits")
    risk_hits = _numeric_column(out, "risk_hits")
    gossip_hits = _numeric_column(out, "gossip_hits")
    squeeze_hits = _numeric_column(out, "squeeze_hits")
    long_term_hits = _numeric_column(out, "long_term_hits")

    if "sentiment_rank" in out.columns:
        sentiment_component = _percentile_score(_numeric_column(out, "sentiment_rank"), higher_is_better=False)
    else:
        sentiment_component = pd.Series(50.0, index=out.index)

    out["numeric_score"] = (
        _percentile_score(change)
        + _percentile_score(volume)
        + _percentile_score(news_count)
    ) / 3
    out["keyword_score"] = (
        _percentile_score(keyword_hits)
        + _percentile_score(catalyst_hits)
        + _percentile_score(squeeze_hits)
        + _percentile_score(long_term_hits) * 0.50
        - (_percentile_score(risk_hits) * 0.35)
        - (_percentile_score(gossip_hits) * 0.20)
    ).clip(0, 100)
    out["ai_signal_score"] = (
        out["numeric_score"] * 0.40
        + sentiment_component * 0.25
        + _percentile_score(news_count) * 0.15
        + out["keyword_score"] * 0.20
    ).round(1)
    out["short_squeeze_score"] = (
        _percentile_score(change) * 0.30
        + _percentile_score(volume) * 0.30
        + _percentile_score(squeeze_hits) * 0.25
        + (100 - _percentile_score(price)) * 0.15
    ).round(1)
    out["long_term_score"] = (
        sentiment_component * 0.35
        + _percentile_score(long_term_hits) * 0.25
        + _percentile_score(news_count) * 0.20
        + (100 - _percentile_score(abs(change))) * 0.20
    ).round(1)
    out["risk_flag"] = risk_hits.map(lambda v: "High" if v >= 2 else ("Watch" if v == 1 else "Low"))
    out["gossip_flag"] = gossip_hits.map(lambda v: "Possible rumor" if v >= 1 else "None")
    out["signal_label"] = out["ai_signal_score"].map(
        lambda v: "Strong watch" if v >= 75 else ("Watch" if v >= 55 else "Low priority")
    )
    out["ai_reason"] = out.apply(_signal_reason, axis=1)
    return out.sort_values("ai_signal_score", ascending=False).reset_index(drop=True)


def _signal_reason(row: pd.Series) -> str:
    reasons: list[str] = []
    change = pd.to_numeric(pd.Series([row.get("change_pct")]), errors="coerce").fillna(0).iloc[0]
    volume = pd.to_numeric(pd.Series([row.get("volume")]), errors="coerce").fillna(0).iloc[0]
    news_count = pd.to_numeric(pd.Series([row.get("news_count")]), errors="coerce").fillna(0).iloc[0]
    keyword_hits = pd.to_numeric(pd.Series([row.get("keyword_hits")]), errors="coerce").fillna(0).iloc[0]
    squeeze_score = pd.to_numeric(pd.Series([row.get("short_squeeze_score")]), errors="coerce").fillna(0).iloc[0]
    long_term_score = pd.to_numeric(pd.Series([row.get("long_term_score")]), errors="coerce").fillna(0).iloc[0]
    if abs(change) >= 10:
        reasons.append("large price move")
    if volume >= 1_000_000:
        reasons.append("high volume")
    if news_count >= 3:
        reasons.append("active news flow")
    if keyword_hits >= 1:
        reasons.append(f"keyword group: {row.get('top_keyword_group', 'None')}")
    if squeeze_score >= 70:
        reasons.append("short-squeeze watch")
    if long_term_score >= 70:
        reasons.append("long-term watch")
    if row.get("gossip_flag") == "Possible rumor":
        reasons.append("rumor/gossip wording")
    if row.get("risk_flag") in {"High", "Watch"}:
        reasons.append("risk language")
    return "; ".join(reasons) if reasons else "baseline screener and sentiment signal"


def build_message_keyword_flags(messages: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "ticker",
        "title",
        "published",
        "url",
        "keyword_hits",
        "top_keyword_group",
        "gossip_hits",
        "squeeze_hits",
        "risk_hits",
    ]
    if messages.empty:
        return pd.DataFrame(columns=columns)

    work = messages.copy()
    if "ticker" in work.columns:
        work["ticker"] = work["ticker"].astype(str).str.upper()
    else:
        work["ticker"] = ""
    title = work["title"].astype(str) if "title" in work.columns else pd.Series("", index=work.index)
    summary = work["summary"].astype(str) if "summary" in work.columns else pd.Series("", index=work.index)
    work["_keyword_text"] = (title + " " + summary).str.lower()
    group_keys: list[tuple[str, str]] = []
    for group, terms in KEYWORD_GROUPS.items():
        key = _keyword_group_key(group) + "_hits"
        pattern = "|".join(re.escape(term.lower()) for term in terms)
        work[key] = work["_keyword_text"].str.contains(pattern, na=False).astype(int) if pattern else 0
        group_keys.append((group, key))
    hit_cols = [key for _, key in group_keys]
    work["keyword_hits"] = work[hit_cols].sum(axis=1)

    def _top_group(row: pd.Series) -> str:
        hits = [(group, int(row.get(key, 0))) for group, key in group_keys]
        hits = [item for item in hits if item[1] > 0]
        return max(hits, key=lambda item: item[1])[0] if hits else "None"

    work["top_keyword_group"] = work.apply(_top_group, axis=1)
    for col in columns:
        if col not in work.columns:
            work[col] = "" if col in {"ticker", "title", "published", "url", "top_keyword_group"} else 0
    return work[columns].sort_values(["keyword_hits", "published"], ascending=[False, False]).reset_index(drop=True)


def render_signal_scanner(filtered: pd.DataFrame, scored: pd.DataFrame, tickers: list[str]) -> None:
    st.subheader("AI + Numeric Signal Scanner")
    st.caption(
        "Prototype scanner for the professor checklist: dictionary keywords, numeric screener signals, "
        "AI-style combined ranking, short-squeeze proxy, and long-term watchlist hints. "
        "Scores are decision-support signals, not trading recommendations."
    )
    signals = build_signal_dashboard_table(filtered, scored, tickers)
    if signals.empty:
        st.info("No ticker rows available for signal scanning.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Scanned tickers", len(signals))
    c2.metric("Strong watches", int((signals["ai_signal_score"] >= 75).sum()))
    c3.metric("Squeeze watch", int((signals["short_squeeze_score"] >= 70).sum()))
    c4.metric("Risk flags", int(signals["risk_flag"].isin(["High", "Watch"]).sum()))

    min_ai_score = st.slider("Minimum AI signal score", 0, 100, 0, key="min_ai_signal_score")
    show_risk = st.checkbox("Include risk-flagged tickers", value=True, key="include_risk_flagged")
    view = signals[signals["ai_signal_score"] >= min_ai_score].copy()
    if not show_risk:
        view = view[view["risk_flag"] == "Low"]

    cols = [
        c
        for c in (
            "ticker",
            "company",
            "signal_label",
            "ai_signal_score",
            "numeric_score",
            "short_squeeze_score",
            "long_term_score",
            "keyword_hits",
            "top_keyword_group",
            "risk_flag",
            "gossip_flag",
            "gossip_hits",
            "ai_reason",
            "change_pct",
            "volume",
            "news_count",
            "sentiment_rank",
        )
        if c in view.columns
    ]
    st.dataframe(
        view[cols].head(30),
        width="stretch",
        hide_index=True,
        column_config={
            "ai_signal_score": st.column_config.NumberColumn(format="%.1f"),
            "numeric_score": st.column_config.NumberColumn(format="%.1f"),
            "short_squeeze_score": st.column_config.NumberColumn(format="%.1f"),
            "long_term_score": st.column_config.NumberColumn(format="%.1f"),
            "change_pct": st.column_config.NumberColumn(format="%.2f"),
            "volume": st.column_config.NumberColumn(format="%d"),
        },
    )
    squeeze_view = view[view["short_squeeze_score"] >= 70].copy()
    if not squeeze_view.empty:
        with st.expander("Short squeeze watch candidates", expanded=False):
            squeeze_cols = [
                c
                for c in (
                    "ticker",
                    "company",
                    "short_squeeze_score",
                    "change_pct",
                    "volume",
                    "squeeze_hits",
                    "gossip_flag",
                    "ai_reason",
                )
                if c in squeeze_view.columns
            ]
            st.dataframe(squeeze_view[squeeze_cols].head(15), width="stretch", hide_index=True)
    st.download_button(
        "Download signal scanner CSV",
        view.to_csv(index=False).encode("utf-8"),
        file_name="signal_scanner.csv",
        mime="text/csv",
        width="stretch",
    )

    with st.expander("How these prototype scores map to the professor checklist", expanded=False):
        st.markdown(
            "- **Keyword selections:** counts catalyst, risk, squeeze, and long-term terms in live Finviz news.\n"
            "- **Gossip detection:** flags rumor-style words such as rumor, heard, leak, pump, and unconfirmed.\n"
            "- **Numeric screener:** uses live change %, volume, price, and news count from the Finviz screener/news layer.\n"
            "- **AI ranking:** combines numeric score, sentiment rank, news activity, and keyword score into one watch score.\n"
            "- **Short squeeze:** proxy score based on price move, volume, low-price pressure, and squeeze keywords.\n"
            "- **Long-term scan:** proxy score based on positive sentiment, long-term keywords, news depth, and lower volatility.\n"
            "- **Sorting/thresholding:** use the score slider and download/export for review."
        )


def render_tradingview_screener() -> None:
    st.subheader("TradingView Numeric Screener")
    st.caption(
        "Secondary numeric screener source from TradingView's public scanner. "
        "This is used for comparison with the Finviz screener and does not require a TradingView login for these fields."
    )
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    top_n = c1.number_input("Rows", min_value=5, max_value=100, value=20, step=5, key="tv_top_n")
    min_volume = c2.number_input(
        "Minimum volume",
        min_value=0,
        max_value=50_000_000,
        value=100_000,
        step=50_000,
        key="tv_min_volume",
    )
    sort_by = c3.selectbox(
        "Sort by",
        ["change", "volume", "market_cap_basic", "relative_volume_10d_calc", "premarket_change", "postmarket_change"],
        index=0,
        key="tv_sort_by",
    )
    sort_order = c4.selectbox("Order", ["desc", "asc"], index=0, key="tv_sort_order")
    if st.button("Refresh TradingView", key="refresh_tradingview"):
        load_tradingview_screener.clear()
        st.rerun()

    try:
        frame = load_tradingview_screener(int(top_n), int(min_volume), str(sort_by), str(sort_order))
    except Exception as exc:  # noqa: BLE001
        st.warning(f"TradingView screener is temporarily unavailable: {_safe_error_text(exc)}")
        return

    if frame.empty:
        st.info("TradingView returned no screener rows for the selected filters.")
        return

    m1, m2, m3 = st.columns(3)
    m1.metric("TradingView rows", len(frame))
    if "change_pct" in frame.columns:
        m2.metric("Mean change %", f"{pd.to_numeric(frame['change_pct'], errors='coerce').mean():.2f}%")
    if "volume" in frame.columns:
        m3.metric("Total volume", f"{pd.to_numeric(frame['volume'], errors='coerce').fillna(0).sum():,.0f}")

    cols = [
        c
        for c in (
            "screener_rank",
            "ticker",
            "company",
            "exchange",
            "price",
            "change_pct",
            "volume",
            "market_cap",
            "premarket_change_pct",
            "postmarket_change_pct",
            "relative_volume_10d",
            "sector",
            "industry",
            "source_url",
            "fetched_at",
        )
        if c in frame.columns
    ]
    st.dataframe(
        frame[cols],
        width="stretch",
        hide_index=True,
        column_config={
            "price": st.column_config.NumberColumn(format="$%.4f"),
            "change_pct": st.column_config.NumberColumn(format="%.2f%%"),
            "premarket_change_pct": st.column_config.NumberColumn(format="%.2f%%"),
            "postmarket_change_pct": st.column_config.NumberColumn(format="%.2f%%"),
            "volume": st.column_config.NumberColumn(format="%d"),
            "market_cap": st.column_config.NumberColumn(format="%.0f"),
            "relative_volume_10d": st.column_config.NumberColumn(format="%.2f"),
            "source_url": st.column_config.LinkColumn("TradingView page"),
        },
    )
    st.download_button(
        "Download TradingView screener CSV",
        frame.to_csv(index=False).encode("utf-8"),
        file_name="tradingview_screener.csv",
        mime="text/csv",
        width="stretch",
    )


def render_professor_checklist() -> None:
    st.subheader("Professor Checklist Coverage")
    st.caption(
        "This page separates completed dashboard features from prototype signal layers and future infrastructure work. "
        "It is meant to make the project scope clear during the final demo."
    )
    rows = [
        ("Brokers news", "Prototype", "Can be added as broker/news source modules; no broker account integration yet."),
        ("Finviz news screener", "Done", "Live Finviz screener, quote/news pages, filters, ranking, and chart tab."),
        ("TradingView numeric screener", "Done", "Public TradingView scanner endpoint is available through src.collect_tradingview and the API wrapper."),
        ("Global/PR/SEC/FDA/RSS news", "Done", "Public RSS feeds are wired through collect_news.py for GlobeNewswire, PR Newswire, SEC, FDA, and custom RSS URLs."),
        ("Business Wire/Access/Benzinga/Dow Jones feeds", "Prototype", "The source framework is ready; stable production use needs licensed feeds or reliable public endpoints."),
        ("Keyword dictionary selections", "Done", "Signals and Social tabs scan catalyst, risk, gossip, squeeze, and long-term terms."),
        ("Stocktwits social sourcing", "Done", "Stocktwits chart, parsed messages when available, WebSocket quote check."),
        ("X/Reddit/Bluesky social sourcing", "Future", "Needs stable API/account access; not enabled in final demo path."),
        ("Gossip detection", "Prototype", "Dictionary layer flags rumor-style Stocktwits/news language; deeper classifier is future work."),
        ("Rolling window", "Done", "Stocktwits chart ranges and Finviz optional K-line window."),
        ("AI rankings", "Prototype", "AI-style score combines sentiment, numeric rank, news count, keywords, and an explanation reason."),
        ("Numeric screeners", "Done", "Finviz change %, volume, price, news count, sorting, thresholding."),
        ("AI numeric ranking", "Prototype", "Signals tab combines numeric score with sentiment/news/keyword signals."),
        ("Sorting and thresholding", "Done", "Ranked table sort controls and Signals score threshold slider."),
        ("Correlation", "Done", "Correlation analysis for price change vs volume/social indicators."),
        ("CVD high-resolution chart signals", "Prototype", "Volume/price chart signals exist; true CVD requires trade-level bid/ask data."),
        ("Long-term scans", "Prototype", "Long-term watch score from sentiment, news depth, and long-term keywords."),
        ("Arbitrage", "Future", "Needs multi-venue price feeds and execution assumptions."),
        ("Google Trends", "Future", "Can be added through pytrends/API; not required for stable final demo."),
        ("Short squeeze", "Prototype", "Short-squeeze proxy score from volume, price move, low-price pressure, and keywords."),
        ("Options", "Future", "Needs options chain source."),
        ("Futures", "Future", "Needs futures market data source."),
        ("Alerts", "Done", "Realtime, chart-window, social latest alerts plus configurable thresholds and export."),
        ("AI Agent/Learning", "Prototype", "Signal workflow is automated; fully autonomous agent is future work."),
        ("Broker trading / bracket orders", "Future", "Needs real broker API credentials, permissions, and safety controls."),
        ("RAM/database architecture", "Prototype", "Session cache and optional Mongo module exist; Redis/Kafka production pipeline is future work."),
        ("Project API", "Done", "FastAPI wrapper exposes health and Stocktwits snapshot endpoints."),
        ("Public deployment package", "Done", "Procfile and railway.toml are included for Railway Streamlit deployment."),
        ("Demo and technical recording prep", "Done", "Demo script, technical recording script, delivery guide, and AI prompt log are included."),
        ("Data freshness monitoring", "Done", "Social tab shows chart latest time, WebSocket check time, quote latest time, and social latest time."),
        ("Exportable evidence", "Done", "Ranked table CSV, signal scanner CSV, alert log CSV, checklist CSV, and ticker report export are available."),
    ]
    frame = pd.DataFrame(rows, columns=["item", "status", "implementation"])
    status_order = st.multiselect(
        "Status filter",
        ["Done", "Prototype", "Future"],
        default=["Done", "Prototype", "Future"],
        key="checklist_status_filter",
    )
    if status_order:
        frame = frame[frame["status"].isin(status_order)]
    st.dataframe(frame, width="stretch", hide_index=True)
    done = int((frame["status"] == "Done").sum())
    prototype = int((frame["status"] == "Prototype").sum())
    future = int((frame["status"] == "Future").sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("Done", done)
    c2.metric("Prototype", prototype)
    c3.metric("Future work", future)
    st.download_button(
        "Download checklist CSV",
        frame.to_csv(index=False).encode("utf-8"),
        file_name="professor_checklist_coverage.csv",
        mime="text/csv",
        width="stretch",
    )
    st.info(
        "Final demo focus: Finviz live screener/news, Stocktwits chart + social indicators, one-minute current-session "
        "quote monitoring, alerts, correlation, and exportable evidence. Items marked Future are listed honestly because "
        "they require broker permissions, paid feeds, or production infrastructure."
    )


def render_export_report(
    *,
    chart_ticker: str,
    filtered: pd.DataFrame,
    scored: pd.DataFrame,
    window_label: str,
    stocktwits_range_label: str,
    alert_settings: dict[str, float],
) -> None:
    st.subheader("Current Demo Report Export")
    st.caption("Generate a short Markdown report for the selected ticker and current dashboard settings.")
    ticker = chart_ticker.upper()
    ticker_row = filtered[filtered["ticker"].astype(str).str.upper() == ticker].head(1)
    news_rows = scored[scored["ticker"].astype(str).str.upper() == ticker].copy() if not scored.empty else pd.DataFrame()
    signal_rows = build_signal_dashboard_table(filtered, scored, filtered["ticker"].astype(str).str.upper().tolist())
    signal_row = signal_rows[signal_rows["ticker"].astype(str).str.upper() == ticker].head(1)
    lines = [
        f"# {ticker} Dashboard Report",
        "",
        f"- Generated: {datetime.now(DISPLAY_TZ).strftime(f'%Y-%m-%d %H:%M:%S {DISPLAY_TZ_LABEL}')}",
        f"- Finviz news window: {window_label}",
        f"- Stocktwits chart range: {stocktwits_range_label}",
        "",
        "## Screener Snapshot",
    ]
    if ticker_row.empty:
        lines.append("- No current screener row for this ticker.")
    else:
        row = ticker_row.iloc[0]
        for col in ["company", "price", "change_pct", "volume", "news_count", "sentiment_rank", "message_density"]:
            if col in row.index:
                lines.append(f"- {col}: {row.get(col)}")
    lines.append("")
    lines.append("## Signal Snapshot")
    if signal_row.empty:
        lines.append("- No signal row generated.")
    else:
        row = signal_row.iloc[0]
        for col in [
            "ai_signal_score",
            "numeric_score",
            "short_squeeze_score",
            "long_term_score",
            "top_keyword_group",
            "risk_flag",
            "gossip_flag",
            "ai_reason",
        ]:
            if col in row.index:
                lines.append(f"- {col}: {row.get(col)}")
    lines.append("")
    lines.append("## Top AI Watchlist")
    top_cols = ["ticker", "ai_signal_score", "short_squeeze_score", "risk_flag", "gossip_flag", "ai_reason"]
    top_cols = [c for c in top_cols if c in signal_rows.columns]
    if signal_rows.empty or not top_cols:
        lines.append("- No AI watchlist rows generated.")
    else:
        for _, row in signal_rows[top_cols].head(5).iterrows():
            reason = row.get("ai_reason", "")
            lines.append(
                f"- {row.get('ticker')}: AI {row.get('ai_signal_score')}, "
                f"squeeze {row.get('short_squeeze_score')}, risk {row.get('risk_flag')}, "
                f"gossip {row.get('gossip_flag')} - {reason}"
            )
    lines.append("")
    lines.append("## Implemented Professor Checklist Evidence")
    lines.extend(
        [
            "- Live Finviz news screener with sorting and thresholding.",
            "- Stocktwits chart with price, stock volume, sentiment, message volume, and one-minute current-session quote checks.",
            "- Keyword dictionary scanner for catalyst, risk, gossip, squeeze, and long-term terms.",
            "- AI-style numeric ranking that combines screener, sentiment, news activity, and keyword signals.",
            "- Short-squeeze proxy score, correlation analysis, realtime/chart/social alerts, and CSV exports.",
        ]
    )
    lines.append("")
    lines.append("## Alert Settings")
    for key, value in alert_settings.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Latest News Headlines")
    if news_rows.empty:
        lines.append("- No live Finviz news in the selected window.")
    else:
        for _, item in news_rows.head(8).iterrows():
            lines.append(f"- {item.get('published', '')}: {item.get('title', '')}")
    report = "\n".join(lines)
    st.download_button(
        "Download current ticker report",
        report.encode("utf-8"),
        file_name=f"{ticker.lower()}_demo_report.md",
        mime="text/markdown",
        width="stretch",
    )
    with st.expander("Preview report", expanded=False):
        st.markdown(report)


def _finviz_auth_help(exc: Exception) -> str | None:
    text = str(exc)
    if "401" in text or "Unauthorized" in text:
        return (
            "**Finviz API token rejected (401).** Regenerate it: log in at "
            "[elite.finviz.com](https://elite.finviz.com) ->**Settings ->API** ->copy token ->"
            "update `FINVIZ_API_TOKEN` in `.env` ->restart Streamlit."
        )
    return None


def _safe_error_text(exc: Exception) -> str:
    """Hide API tokens in URLs before displaying exceptions in Streamlit."""
    return re.sub(r"auth=[^&\\s]+", "auth=REDACTED", str(exc))


def subtract_months(value, months: int):
    year = value.year
    month = value.month - months
    while month <= 0:
        month += 12
        year -= 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _company_for_ticker(screener: pd.DataFrame, ticker: str) -> str:
    if screener.empty or "company" not in screener.columns:
        return ""
    match = screener[screener["ticker"].astype(str).str.upper() == ticker.upper()]
    if match.empty:
        return ""
    return str(match.iloc[0].get("company", "") or "")


def render_live_chart(
    chart_ticker: str,
    company: str,
    period_label: str,
    token: str,
    *,
    sma_periods: tuple[int, ...],
    live_screener: pd.DataFrame,
    live_news: pd.DataFrame,
    chart_window_start=None,
    chart_window_end=None,
    chart_window_label: str = "all bars",
    apply_chart_window: bool = False,
) -> None:
    period_code = PERIOD_OPTIONS[period_label]
    stock_url = build_elite_stock_url(chart_ticker, token, period=period_code)

    live_change_pct: float | None = None
    if not live_screener.empty and "change_pct" in live_screener.columns:
        match = live_screener[live_screener["ticker"].astype(str).str.upper() == chart_ticker.upper()]
        if not match.empty:
            val = match.iloc[0]["change_pct"]
            if pd.notna(val):
                live_change_pct = float(val)

    try:
        bars = load_live_bars(chart_ticker, period_code, token)
        if apply_chart_window:
            chart_bars = filter_bars_by_date_window(
                bars,
                window_start=chart_window_start,
                window_end=chart_window_end,
            )
            window_label_for_chart = chart_window_label
        else:
            chart_bars = bars
            window_label_for_chart = None

        if chart_bars.empty:
            st.warning(
                f"No {period_label} bars in the selected K-line window (**{chart_window_label}**). "
                "Try a wider range or turn off **Enable Finviz K-line rolling window**."
            )
            return

        live = latest_price_info(chart_bars)
        if apply_chart_window:
            window_chg = window_change_pct(chart_bars)
            display_change = window_chg if window_chg is not None else live_change_pct
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Last (in window)", f"{live.get('price', 0):.4f}")
            c2.metric(f"Change % ({chart_window_label})", f"{display_change:+.2f}%" if display_change is not None else "N/A")
            c3.metric("Bars in window", len(chart_bars))
            c4.metric("Last bar volume", f"{int(live.get('volume', 0)):,}")
        else:
            display_change = live_change_pct if live_change_pct is not None else live.get("change_pct")
            c1, c2, c3 = st.columns(3)
            c1.metric("Last (live API)", f"{live.get('price', 0):.4f}")
            c2.metric(f"Change % ({period_label})", f"{display_change:+.2f}%")
            c3.metric("Last bar volume", f"{int(live.get('volume', 0)):,}")

        fig = build_finviz_style_chart(
            chart_bars,
            ticker=chart_ticker,
            company=company,
            change_pct=display_change,
            period_label=period_label,
            sma_periods=sma_periods,
            window_label=window_label_for_chart,
        )
        st.plotly_chart(fig, use_container_width=True)
        cap = f"Live Finviz Elite `quote_export` - **{len(chart_bars)}** bars"
        if apply_chart_window:
            cap += f" in **{chart_window_label}** (UTC)"
        else:
            cap += " (full series)"
        cap += f" - [Open in Finviz]({stock_url})"
        st.caption(cap)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load live chart for {chart_ticker}: {_safe_error_text(exc)}")
        auth_help = _finviz_auth_help(exc)
        if auth_help:
            st.info(auth_help)

    ticker_news = live_news[live_news["ticker"].astype(str).str.upper() == chart_ticker.upper()]
    if ticker_news.empty:
        st.markdown(f":red[**{chart_ticker}** -no Finviz news (news-free)]")
    else:
        for _, item in ticker_news.head(10).iterrows():
            title = item.get("title", "")
            url = item.get("url", "")
            published = item.get("published", "")
            if url:
                st.markdown(f"- {published} - [{title}]({url})")
            else:
                st.markdown(f"- {published} - {title}")


DENSITY_DISPLAY = {
    "low": "Sparse",
    "medium": "Moderate",
    "high": "Dense",
}


def _format_density_label(value: object) -> str:
    key = str(value).strip().lower()
    return DENSITY_DISPLAY.get(key, str(value) if pd.notna(value) and str(value).strip() else "N/A")


def render_ranked_table(filtered: pd.DataFrame, *, window_label: str) -> None:
    st.caption(
        f"**news_count** = live Finviz articles with published date in **{window_label}**. "
        "**message_density**: Sparse (0-), Moderate (2-), Dense (4+)."
    )
    cols = [
        c
        for c in (
            "screener_rank",
            "sentiment_rank",
            "ticker",
            "company",
            "sector",
            "price",
            "change_pct",
            "volume",
            "news_count",
            "message_density",
        )
        if c in filtered.columns
    ]
    view = filtered[cols].copy()
    if "news_count" in view.columns:
        view["news_count"] = view["news_count"].where(view["news_count"].notna(), "N/A")
    if "message_density" in view.columns:
        view["message_density"] = view["message_density"].map(_format_density_label)
    st.dataframe(
        view,
        width="stretch",
        hide_index=True,
        column_config={
            "price": st.column_config.NumberColumn(format="%.2f"),
            "change_pct": st.column_config.NumberColumn(format="%.2f", help="Live Finviz screener"),
            "volume": st.column_config.NumberColumn(format="%d"),
            "news_count": st.column_config.TextColumn(
                help=f"Live Finviz articles in range: {window_label}"
            ),
            "message_density": st.column_config.TextColumn(
                help="Sparse: 0-1 articles - Moderate: 2-3 - Dense: 4+ (same date range as news_count)"
            ),
        },
    )
    safe_label = "".join(ch if ch.isalnum() else "_" for ch in window_label).strip("_") or "all"
    st.download_button(
        "Download ranked tickers CSV",
        data=view.to_csv(index=False).encode("utf-8"),
        file_name=f"ranked_tickers_{safe_label}.csv",
        mime="text/csv",
        width="stretch",
    )


def render_news_viewer(scored: pd.DataFrame) -> None:
    if scored.empty:
        st.info("No live Finviz news returned for current screener tickers.")
        return

    filtered = scored.copy()
    query = st.text_input(
        "Search news titles",
        key="live_news_search",
        placeholder="Keyword, company, catalyst...",
    ).strip()
    if query and "title" in filtered.columns:
        filtered = filtered[filtered["title"].astype(str).str.contains(query, case=False, regex=False, na=False)]

    if "sentiment_label" in filtered.columns:
        sentiment_options = sorted(
            label for label in filtered["sentiment_label"].dropna().astype(str).unique() if label.strip()
        )
        selected_sentiments = st.multiselect(
            "Sentiment filter",
            options=sentiment_options,
            default=sentiment_options,
            key="live_news_sentiment_filter",
        )
        if selected_sentiments:
            filtered = filtered[filtered["sentiment_label"].astype(str).isin(selected_sentiments)]

    available = sorted(filtered["ticker"].astype(str).str.upper().unique())
    if not available:
        st.info("No live Finviz articles match the current news filters.")
        return

    selected = st.selectbox("Select ticker", available, key="live_news_ticker")
    news_cols = [
        c
        for c in ("title", "sentiment_label", "sentiment_compound", "source", "published", "url")
        if c in filtered.columns
    ]
    ticker_news = filtered[filtered["ticker"].astype(str).str.upper() == selected][news_cols]
    st.write(f"**{len(ticker_news)}** live Finviz articles for **{selected}**")
    st.dataframe(ticker_news, use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered news CSV",
        data=filtered[news_cols].to_csv(index=False).encode("utf-8"),
        file_name="finviz_live_news_filtered.csv",
        mime="text/csv",
        width="stretch",
    )


def filter_messages_by_time_window(
    messages: pd.DataFrame,
    *,
    time_start: datetime_time,
    time_end: datetime_time,
) -> pd.DataFrame:
    """Keep messages whose UTC time-of-day falls in the selected intraday window."""
    if messages.empty or "published" not in messages.columns:
        return messages.copy()

    out = messages.copy()
    published = pd.to_datetime(out["published"], errors="coerce", utc=True)
    msg_time = published.dt.time
    if time_start <= time_end:
        mask = (msg_time >= time_start) & (msg_time <= time_end)
    else:
        mask = (msg_time >= time_start) | (msg_time <= time_end)
    return out[mask.fillna(False)].copy()


def render_stocktwits_volume_chart(
    messages: pd.DataFrame,
    *,
    chart_ticker: str,
    token: str,
    window_label: str,
    time_label: str,
    chart_unit: str,
    window_start,
    window_end,
) -> None:
    """Show Stocktwits message volume inside the selected rolling window."""
    st.subheader("Stocktwits message volume")
    if chart_unit == "monthly":
        periods = pd.period_range(
            start=pd.Timestamp(window_start).to_period("M"),
            end=pd.Timestamp(window_end).to_period("M"),
            freq="M",
        )
        axis = pd.DataFrame({"bucket": periods.astype(str)})
        bucket_title = "Month"
        xaxis_title = "Published month (UTC)"
        bar_name = "Monthly posts"
        price_period = PERIOD_OPTIONS["D"]
    elif chart_unit == "daily":
        days = pd.date_range(start=window_start, end=window_end, freq="D")
        axis = pd.DataFrame({"bucket": days.strftime("%Y-%m-%d")})
        bucket_title = "Day"
        xaxis_title = "Published date (UTC)"
        bar_name = "Daily posts"
        price_period = PERIOD_OPTIONS["D"]
    else:
        axis = pd.DataFrame({"bucket": [f"{hour:02d}:00" for hour in range(24)]})
        bucket_title = "Hour"
        xaxis_title = "Published time of day (UTC)"
        bar_name = "Hourly posts"
        price_period = PERIOD_OPTIONS["1H"]

    if messages.empty or "published" not in messages.columns:
        counts = pd.DataFrame(columns=["bucket", "posts"])
        sentiment_by_bucket = pd.DataFrame(columns=["bucket", "sentiment_score"])
        st.caption(f"No Stocktwits messages in this selection; showing the full {bucket_title.lower()} axis.")
    else:
        work = messages.copy()
        work["published_dt"] = pd.to_datetime(work["published"], errors="coerce", utc=True)
        work = work.dropna(subset=["published_dt"])
        if work.empty:
            counts = pd.DataFrame(columns=["bucket", "posts"])
            sentiment_by_bucket = pd.DataFrame(columns=["bucket", "sentiment_score"])
            st.caption(f"No Stocktwits messages with parseable timestamps; showing the full {bucket_title.lower()} axis.")
        else:
            if chart_unit == "monthly":
                work["bucket"] = work["published_dt"].dt.strftime("%Y-%m")
            elif chart_unit == "daily":
                work["bucket"] = work["published_dt"].dt.strftime("%Y-%m-%d")
            else:
                work["bucket"] = work["published_dt"].dt.strftime("%H:00")
            counts = (
                work.groupby("bucket", as_index=False)
                .size()
                .rename(columns={"size": "posts"})
                .sort_values("bucket")
            )
            scored_work = analyze_dataframe(work, engine=LIVE_SCORE_ENGINE)
            sentiment_by_bucket = (
                scored_work.groupby("bucket", as_index=False)["sentiment_compound"]
                .mean()
                .rename(columns={"sentiment_compound": "sentiment_compound_avg"})
            )
            sentiment_by_bucket["sentiment_score"] = (
                (sentiment_by_bucket["sentiment_compound_avg"] + 1.0) * 50
            ).clip(0, 100)
    volume = axis.merge(counts, on="bucket", how="left")
    volume = volume.merge(sentiment_by_bucket[["bucket", "sentiment_score"]], on="bucket", how="left")
    volume["posts"] = volume["posts"].fillna(0).astype(int)

    try:
        price_bars = load_live_bars(chart_ticker, price_period, token)
        price_bars = filter_bars_by_date_window(
            price_bars,
            window_start=window_start,
            window_end=window_end,
        )
    except Exception as exc:  # noqa: BLE001
        price_bars = pd.DataFrame()
        st.caption(f"Price overlay unavailable for {chart_ticker}: {_safe_error_text(exc)}")

    if not price_bars.empty:
        price_work = price_bars.copy()
        price_work["datetime"] = pd.to_datetime(price_work["datetime"], errors="coerce", utc=True)
        price_work = price_work.dropna(subset=["datetime", "close"])
        if chart_unit == "monthly":
            price_work["bucket"] = price_work["datetime"].dt.strftime("%Y-%m")
        elif chart_unit == "daily":
            price_work["bucket"] = price_work["datetime"].dt.strftime("%Y-%m-%d")
        else:
            price_work["bucket"] = price_work["datetime"].dt.strftime("%H:00")
        price_series = (
            price_work.sort_values("datetime")
            .groupby("bucket", as_index=False)
            .tail(1)[["bucket", "close"]]
            .rename(columns={"close": "price"})
        )
        volume = volume.merge(price_series, on="bucket", how="left")
    else:
        volume["price"] = pd.NA

    def sentiment_bar_color(value: object) -> str:
        if pd.isna(value):
            return "#90a4b8"
        score = float(value)
        if score >= 58:
            return "#14b883"
        if score <= 42:
            return "#f05d5e"
        return "#90a4b8"

    volume["sentiment_label"] = volume["sentiment_score"].map(
        lambda value: "N/A" if pd.isna(value) else f"{float(value):.1f}"
    )
    max_posts = max(int(volume["posts"].max()), 1)
    volume["volume_avg"] = volume["posts"].rolling(3, min_periods=1).mean()
    volume["sentiment_scaled"] = volume["sentiment_score"].map(
        lambda value: pd.NA if pd.isna(value) else (float(value) / 100.0) * max_posts
    )
    bar_colors = volume["sentiment_score"].map(sentiment_bar_color)

    price_points = volume[volume["price"].notna()].copy()
    has_price_line = len(price_points) >= 2
    if not price_points.empty and not has_price_line:
        st.caption(
            f"Finviz returned only {len(price_points)} price bucket for {chart_ticker.upper()} in this view, "
            "so the price panel is hidden instead of showing a misleading single-point line."
        )
    fig = make_subplots(
        rows=2 if has_price_line else 1,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.045,
        row_heights=[0.64, 0.36] if has_price_line else None,
    )
    volume_row = 2 if has_price_line else 1
    if has_price_line:
        fig.add_trace(
            go.Scatter(
                x=price_points["bucket"],
                y=price_points["price"],
                name=f"{chart_ticker.upper()} price",
                mode="lines",
                line=dict(color="#089981", width=2.6),
                connectgaps=False,
                hovertemplate="Price: $%{y:.4f}<extra></extra>",
                showlegend=True,
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=price_points["bucket"],
                y=price_points["price"],
                mode="markers",
                name=f"{chart_ticker.upper()} price point",
                marker=dict(size=6, color="#089981", line=dict(width=1, color="#ffffff")),
                hovertemplate="Price: $%{y:.4f}<extra></extra>",
                showlegend=False,
            ),
            row=1,
            col=1,
        )
    fig.add_bar(
        x=volume["bucket"],
        y=volume["posts"],
        name=bar_name,
        marker_color=bar_colors,
        marker_line_color="#ffffff",
        marker_line_width=0.8,
        opacity=0.82,
        width=0.42,
        customdata=volume[["sentiment_label"]],
        hovertemplate="Messages: %{y}<br>Sentiment score: %{customdata[0]}<extra></extra>",
        row=volume_row,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=volume["bucket"],
            y=volume["volume_avg"],
            name="3-bucket volume trend",
            mode="lines",
            line=dict(color="#25313b", width=1.7, dash="dot"),
            hovertemplate="Volume trend: %{y:.1f}<extra></extra>",
        ),
        row=volume_row,
        col=1,
    )
    if volume["sentiment_scaled"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=volume["bucket"],
                y=volume["sentiment_scaled"],
                name="Computed sentiment",
                mode="lines+markers",
                line=dict(color="#0aa6a6", width=2),
                marker=dict(size=6, color="#0aa6a6", line=dict(width=1, color="#ffffff")),
                customdata=volume[["sentiment_label"]],
                hovertemplate="Sentiment score: %{customdata[0]}<br>Scaled to volume axis<extra></extra>",
                connectgaps=False,
            ),
            row=volume_row,
            col=1,
        )
    fig.update_layout(
        title=f"{chart_ticker.upper()} Stocktwits activity lens: {window_label}; {time_label}",
        height=430 if has_price_line else 340,
        margin=dict(l=24, r=24, t=54, b=26),
        hovermode="x unified",
        bargap=0.46,
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    if has_price_line:
        fig.update_xaxes(showgrid=False, categoryorder="array", categoryarray=volume["bucket"].tolist(), row=1, col=1)
    fig.update_xaxes(
        title_text=xaxis_title,
        showgrid=False,
        categoryorder="array",
        categoryarray=volume["bucket"].tolist(),
        row=volume_row,
        col=1,
    )
    if has_price_line:
        fig.update_yaxes(title_text="Price", showgrid=True, gridcolor="#edf1f5", tickprefix="$", row=1, col=1)
    fig.update_yaxes(title_text="Messages", showgrid=True, gridcolor="#edf1f5", rangemode="tozero", row=volume_row, col=1)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Top panel uses the Finviz price line. Bottom panel uses fetched public Stocktwits posts: bars are our message "
        "volume, bar color is our VADER sentiment direction, the dotted line is volume trend, and the teal line is our "
        "computed sentiment scaled onto the volume axis. Locked official Stocktwits sentiment/message-volume metrics are not used."
    )


def render_stocktwits_gateway_chart(detail: dict, *, chart_ticker: str) -> None:
    """Render Stocktwits frontend sentiment/message-volume summary fetched with curl impersonation."""
    timeframes = detail.get("timeframes") if isinstance(detail, dict) else {}
    if not isinstance(timeframes, dict) or not timeframes:
        st.caption("No Stocktwits sentiment gateway timeframes returned for this ticker.")
        return

    order = ["1D", "1W", "1M", "3M", "6M", "1Y", "ALL"]
    rows: list[dict[str, object]] = []
    for label in order:
        item = timeframes.get(label)
        if not isinstance(item, dict) or not item.get("loaded", False):
            continue
        msg = item.get("messageVolume") if isinstance(item.get("messageVolume"), dict) else {}
        sent = item.get("sentiment") if isinstance(item.get("sentiment"), dict) else {}
        rows.append(
            {
                "timeframe": label,
                "message_value": msg.get("value"),
                "message_score": msg.get("valueNormalized"),
                "message_label": msg.get("labelNormalized") or msg.get("label") or "",
                "message_change": msg.get("change"),
                "sentiment_value": sent.get("value"),
                "sentiment_score": sent.get("valueNormalized"),
                "sentiment_label": sent.get("labelNormalized") or sent.get("label") or "",
                "sentiment_change": sent.get("change"),
            }
        )
    if not rows:
        st.caption("Stocktwits sentiment gateway returned no loaded timeframe rows.")
        return

    frame = pd.DataFrame(rows)
    frame["message_value_num"] = pd.to_numeric(frame["message_value"], errors="coerce")
    frame["sentiment_value_num"] = pd.to_numeric(frame["sentiment_value"], errors="coerce")
    frame["sentiment_score_num"] = pd.to_numeric(frame["sentiment_score"], errors="coerce")

    st.subheader("Stocktwits rolling-window metrics")
    st.caption(
        "Each window has its own current snapshot; the chart compares volume and average sentiment across windows."
    )

    for start in range(0, len(frame), 4):
        cols = st.columns(min(4, len(frame) - start))
        for col, (_, row) in zip(cols, frame.iloc[start : start + 4].iterrows()):
            with col:
                msg_value = row["message_value_num"]
                msg_label = str(row["message_label"] or "")
                sent_label = str(row["sentiment_label"] or "")
                sent_value = row["sentiment_value_num"]
                delta = row["message_change"]
                delta_text = None if pd.isna(delta) else f"{float(delta):+.1f}%"
                col.metric(
                    f"{row['timeframe']} message volume",
                    "N/A" if pd.isna(msg_value) else f"{int(msg_value):,}",
                    delta=delta_text,
                )
                sent_text = "N/A" if pd.isna(sent_value) else f"{float(sent_value):.3f}"
                st.caption(f"{msg_label.title() or 'Volume'} - {sent_label.title() or 'Sentiment'} - avg sentiment {sent_text}")

    bar_colors = frame["sentiment_score_num"].map(
        lambda score: "#14b883" if pd.notna(score) and float(score) >= 58 else "#f05d5e" if pd.notna(score) and float(score) <= 42 else "#9db4c8"
    )
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(
        x=frame["timeframe"],
        y=frame["message_value_num"],
        name="Message volume",
        marker_color=bar_colors,
        opacity=0.78,
        customdata=frame[["message_score", "message_label", "message_change"]],
        hovertemplate=(
            "Window: %{x}<br>"
            "Message volume: %{y:,}<br>"
            "Volume score: %{customdata[0]}<br>"
            "Label: %{customdata[1]}<br>"
            "Change: %{customdata[2]}%<extra></extra>"
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=frame["timeframe"],
            y=frame["sentiment_value_num"],
            name="Avg sentiment",
            mode="lines+markers",
            line=dict(color="#25313b", width=2.5),
            marker=dict(size=7, color="#25313b", line=dict(width=1, color="#ffffff")),
            customdata=frame[["sentiment_score", "sentiment_label", "sentiment_change"]],
            hovertemplate=(
                "Window: %{x}<br>"
                "Avg sentiment: %{y:.4f}<br>"
                "Sentiment score: %{customdata[0]}<br>"
                "Label: %{customdata[1]}<br>"
                "Change: %{customdata[2]}%<extra></extra>"
            ),
        ),
        secondary_y=True,
    )
    fig.update_layout(
        title=f"{chart_ticker.upper()} official Stocktwits windows",
        height=360,
        margin=dict(l=24, r=24, t=54, b=26),
        hovermode="x unified",
        bargap=0.44,
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(title_text="Stocktwits window", showgrid=False, categoryorder="array", categoryarray=order)
    fig.update_yaxes(title_text="Message volume", showgrid=True, gridcolor="#edf1f5", rangemode="tozero", secondary_y=False)
    fig.update_yaxes(title_text="Avg sentiment", showgrid=False, range=[-1, 1], secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Fetched from Stocktwits frontend sentiment gateway with curl_cffi browser impersonation. "
        "The bars use Stocktwits message-volume values; the line uses Stocktwits average sentiment. "
        "This does not use the old public API."
    )


def _stocktwits_gateway_rows(detail: dict) -> pd.DataFrame:
    timeframes = detail.get("timeframes") if isinstance(detail, dict) else {}
    if not isinstance(timeframes, dict) or not timeframes:
        return pd.DataFrame()

    order = ["1D", "1W", "1M", "3M", "6M", "1Y", "ALL"]
    rows: list[dict[str, object]] = []
    for label in order:
        item = timeframes.get(label)
        if not isinstance(item, dict) or not item.get("loaded", False):
            continue
        msg = item.get("messageVolume") if isinstance(item.get("messageVolume"), dict) else {}
        sent = item.get("sentiment") if isinstance(item.get("sentiment"), dict) else {}
        rows.append(
            {
                "timeframe": label,
                "message_value": msg.get("value"),
                "message_score": msg.get("valueNormalized"),
                "message_label": msg.get("labelNormalized") or msg.get("label") or "",
                "message_change": msg.get("change"),
                "sentiment_value": sent.get("value"),
                "sentiment_score": sent.get("valueNormalized"),
                "sentiment_label": sent.get("labelNormalized") or sent.get("label") or "",
            }
        )
    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    frame["message_value_num"] = pd.to_numeric(frame["message_value"], errors="coerce")
    frame["message_score_num"] = pd.to_numeric(frame["message_score"], errors="coerce")
    frame["sentiment_value_num"] = pd.to_numeric(frame["sentiment_value"], errors="coerce")
    frame["sentiment_score_num"] = pd.to_numeric(frame["sentiment_score"], errors="coerce")
    return frame


def render_stocktwits_gateway_snapshot(
    detail: dict,
    *,
    chart_ticker: str,
    selected_timeframe: str = "1D",
) -> None:
    """Show official Stocktwits sentiment/message-volume snapshots without plotting them as a fake time series."""
    frame = _stocktwits_gateway_rows(detail)
    if frame.empty:
        st.caption("No Stocktwits sentiment/message-volume gateway metrics returned for this ticker.")
        return

    gateway_label = {
        "1D": "1D",
        "1W": "1W",
        "1M": "1M",
        "3M": "3M",
        "6M": "6M",
        "YTD": "1Y",
        "1Y": "1Y",
        "5Y": "ALL",
        "All": "ALL",
    }.get(selected_timeframe, "1D")
    selected = frame[frame["timeframe"].astype(str) == gateway_label].copy()
    if selected.empty:
        selected = frame.head(1).copy()
    row = selected.iloc[0]

    st.subheader("Sentiment and message volume")
    st.caption(
        f"Gateway snapshot closest to the selected chart range: **{selected_timeframe}**."
    )
    c1, c2, c3 = st.columns(3)
    msg_value = row["message_value_num"]
    delta = row["message_change"]
    delta_text = None if pd.isna(delta) else f"{float(delta):+.1f}%"
    c1.metric(
        "Message Volume",
        "N/A" if pd.isna(msg_value) else f"{int(msg_value):,}",
        delta=delta_text,
    )
    sent_value = row["sentiment_value_num"]
    c2.metric(
        "Sentiment",
        "N/A" if pd.isna(sent_value) else f"{float(sent_value):.3f}",
    )
    c3.metric("Window", str(row["timeframe"]))
    st.caption(
        f"{str(row['message_label'] or 'Volume').title()} / "
        f"{str(row['sentiment_label'] or 'Sentiment').title()}"
    )


def render_stocktwits_style_market_chart(
    *,
    chart_ticker: str,
    token: str,
    messages: pd.DataFrame,
    gateway_detail: dict | None,
    window_start,
    window_end,
    window_label: str,
    time_label: str,
    chart_unit: str,
    stocktwits_range_label: str,
    chart_interaction_mode: str = "Pan",
    realtime_move_threshold: float = 1.5,
    chart_move_threshold: float = 5.0,
    volume_spike_multiple: float = 2.5,
    message_volume_threshold: float = 90.0,
    bullish_sentiment_threshold: float = 80.0,
    bearish_sentiment_threshold: float = 20.0,
    chart_window_slot=None,
) -> None:
    """Draw the Stocktwits-style visible chart: price line over volume bars on one time axis."""
    st.subheader(f"{chart_ticker.upper()} chart")

    zoom = {
        "1D": "1d",
        "1W": "1w",
        "1M": "1m",
        "3M": "3m",
        "6M": "6m",
        "YTD": "ytd",
        "1Y": "1y",
        "5Y": "5y",
        "All": "all",
    }.get(stocktwits_range_label, "1w")

    bars, chart_err = load_stocktwits_chart_data(chart_ticker, zoom)
    chart_source = "Stocktwits chart"
    if bars.empty:
        period_code = PERIOD_OPTIONS["1H"] if chart_unit == "hourly" else PERIOD_OPTIONS["D"]
        period_name = "1-hour" if chart_unit == "hourly" else "daily"
        try:
            bars = load_live_bars(chart_ticker, period_code, token)
            bars = filter_bars_by_date_window(
                bars,
                window_start=window_start,
                window_end=window_end,
            )
            chart_source = "Finviz fallback"
            st.caption(f"Stocktwits chart data unavailable ({chart_err}); using Finviz {period_name} bars.")
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Chart unavailable for {chart_ticker.upper()}: {_safe_error_text(exc)}")
            return

    if bars.empty:
        st.info(f"No chart bars returned for {chart_ticker.upper()} in {window_label}.")
        return

    work = bars.copy()
    work["datetime"] = pd.to_datetime(work["datetime"], errors="coerce", utc=True)
    for col in ("open", "close", "volume"):
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce")
    work = work.dropna(subset=["datetime", "close"]).sort_values("datetime")
    if work.empty:
        st.info(f"No parseable price bars returned for {chart_ticker.upper()} in {window_label}.")
        return
    chart_range_actual = _format_display_range(work["datetime"])
    chart_interval_actual = _format_median_interval(work["datetime"])
    if chart_window_slot is not None:
        chart_window_slot.write(
            f"Chart actual window: **{chart_range_actual}**; "
            f"historical bar interval: **{chart_interval_actual}**"
        )
    chart_dates_et = _to_display_time(work["datetime"]).dt.date.dropna()
    if not chart_dates_et.empty:
        latest_chart_date = chart_dates_et.max()
        today_et = datetime.now(DISPLAY_TZ).date()
        if latest_chart_date < today_et:
            st.warning(
                f"Stocktwits chart data for {chart_ticker.upper()} is stale: latest chart bar is "
                f"**{latest_chart_date} {DISPLAY_TZ_LABEL}**, while today is **{today_et} {DISPLAY_TZ_LABEL}**. "
                f"The chart below shows the latest bars returned by Stocktwits (**{chart_range_actual}**); realtime quote "
                "checks are shown separately in Data freshness when Stocktwits WebSocket returns a newer quote."
            )
        elif chart_window_slot is None:
            st.caption(
                f"Stocktwits chart data range: **{chart_range_actual}**; "
                f"historical bar interval: **{chart_interval_actual}**."
            )
    elif chart_window_slot is None:
        st.caption(
            f"Stocktwits chart data range: **{chart_range_actual}**; "
            f"historical bar interval: **{chart_interval_actual}**."
        )

    realtime_checked_at = datetime.now(timezone.utc)
    realtime_quotes, realtime_err = load_stocktwits_realtime_quotes(chart_ticker)
    if not realtime_quotes.empty:
        realtime_quotes = realtime_quotes.copy()
        realtime_quotes["datetime"] = pd.to_datetime(realtime_quotes["datetime"], errors="coerce", utc=True)
        realtime_quotes["close"] = pd.to_numeric(realtime_quotes["close"], errors="coerce")
        realtime_quotes = realtime_quotes.dropna(subset=["datetime", "close"]).sort_values("datetime")
    if realtime_quotes.empty:
        realtime_quotes = pd.DataFrame(columns=["datetime", "close"])

    live_key = f"stocktwits_live_quote_history::{chart_ticker.upper()}::{stocktwits_range_label}"
    previous_live = st.session_state.get(live_key, pd.DataFrame(columns=["datetime", "close"]))
    live_history = pd.concat(
        [
            previous_live[["datetime", "close"]] if not previous_live.empty else previous_live,
            realtime_quotes[["datetime", "close"]] if not realtime_quotes.empty else realtime_quotes,
        ],
        ignore_index=True,
    )
    if not live_history.empty:
        live_history["datetime"] = pd.to_datetime(live_history["datetime"], errors="coerce", utc=True)
        live_history["close"] = pd.to_numeric(live_history["close"], errors="coerce")
        live_history = live_history.dropna(subset=["datetime", "close"]).sort_values("datetime")
        live_history["minute"] = live_history["datetime"].dt.floor("min")
        live_history = live_history.drop_duplicates(subset=["minute"], keep="last")
        live_history["datetime"] = live_history["minute"]
        live_history = live_history.drop(columns=["minute"])
        start_ts = pd.Timestamp(window_start, tz="UTC")
        end_ts = pd.Timestamp(window_end, tz="UTC") + pd.Timedelta(days=1)
        live_history = live_history[
            (live_history["datetime"] >= start_ts) & (live_history["datetime"] < end_ts)
        ].copy()
    st.session_state[live_key] = live_history
    realtime_quotes = live_history

    latest_realtime_price = None
    latest_realtime_at = pd.NaT
    if not realtime_quotes.empty:
        latest_realtime_row = realtime_quotes.dropna(subset=["datetime", "close"]).tail(1)
        if not latest_realtime_row.empty:
            latest_realtime_price = float(latest_realtime_row["close"].iloc[0])
            latest_realtime_at = latest_realtime_row["datetime"].iloc[0]
    rt_price_label = f"${latest_realtime_price:.4f}" if latest_realtime_price is not None else "N/A"
    rt_time_label = _format_display_time(latest_realtime_at)
    st.caption(
        f"Latest realtime price from Stocktwits WebSocket: **{rt_price_label}** "
        f"at **{rt_time_label}**"
    )

    live_for_chart = realtime_quotes
    live_merge_note = ""
    if not realtime_quotes.empty:
        chart_latest_dt = work["datetime"].dropna().max()
        live_latest_dt = realtime_quotes["datetime"].dropna().max()
        historical_step = pd.to_timedelta(work["datetime"].sort_values().diff().median())
        if pd.isna(historical_step) or historical_step <= pd.Timedelta(0):
            historical_step = pd.Timedelta(minutes=30 if chart_unit == "hourly" else 1_440)
        max_live_gap = max(historical_step * 3, pd.Timedelta(minutes=90))
        gap = live_latest_dt - chart_latest_dt
        chart_latest_date = _to_display_time(pd.Series([chart_latest_dt])).dt.date.iloc[0]
        live_latest_date = _to_display_time(pd.Series([live_latest_dt])).dt.date.iloc[0]
        if pd.notna(gap) and gap > max_live_gap:
            live_merge_note = ""
        elif chart_unit == "hourly" and chart_latest_date != live_latest_date and gap > historical_step:
            live_merge_note = ""
    if not live_for_chart.empty:
        chart_source = f"{chart_source} + Stocktwits websocket live quote"

    if "volume" not in work.columns:
        work["volume"] = 0
    if "open" not in work.columns:
        work["open"] = work["close"]
    if "sentiment_score" not in work.columns:
        work["sentiment_score"] = pd.NA
    if "message_volume_score" not in work.columns:
        work["message_volume_score"] = pd.NA
    work["volume"] = work["volume"].fillna(0)
    work["bar_color"] = work.apply(
        lambda row: "#16c784" if float(row["close"]) >= float(row["open"]) else "#ff4d4f",
        axis=1,
    )

    social_points = work[["datetime", "sentiment_score", "message_volume_score"]].rename(
        columns={"datetime": "bucket_dt"}
    )
    social_points["sentiment_score"] = pd.to_numeric(social_points["sentiment_score"], errors="coerce")
    social_points["message_volume_score"] = pd.to_numeric(social_points["message_volume_score"], errors="coerce")
    social_points = social_points[
        social_points["sentiment_score"].notna()
        | (social_points["message_volume_score"].notna() & (social_points["message_volume_score"] > 0))
    ].copy()
    social_can_extend = True
    if social_points.empty and messages is not None and not messages.empty and "published" in messages.columns:
        msg_work = messages.copy()
        if "ticker" in msg_work.columns:
            msg_work = msg_work[msg_work["ticker"].astype(str).str.upper() == chart_ticker.upper()]
        msg_work["published_dt"] = pd.to_datetime(msg_work["published"], errors="coerce", utc=True)
        msg_work = msg_work.dropna(subset=["published_dt"])
        chart_start_dt = work["datetime"].min()
        chart_end_dt = work["datetime"].max()
        msg_work = msg_work[
            (msg_work["published_dt"] >= chart_start_dt) & (msg_work["published_dt"] <= chart_end_dt)
        ].copy()
        if not msg_work.empty:
            if chart_unit == "hourly":
                msg_work["bucket_dt"] = msg_work["published_dt"].dt.floor("h")
            else:
                msg_work["bucket_dt"] = msg_work["published_dt"].dt.floor("D")
            scored_messages = analyze_dataframe(msg_work, engine=LIVE_SCORE_ENGINE)
            counts = (
                scored_messages.groupby("bucket_dt", as_index=False)
                .size()
                .rename(columns={"size": "message_volume"})
            )
            sentiment = (
                scored_messages.groupby("bucket_dt", as_index=False)["sentiment_compound"]
                .mean()
                .rename(columns={"sentiment_compound": "sentiment_compound_avg"})
            )
            social_points = counts.merge(sentiment, on="bucket_dt", how="left")
            social_points["sentiment_score"] = (
                (social_points["sentiment_compound_avg"] + 1.0) * 50.0
            ).clip(0, 100)
            social_points["message_volume"] = social_points["message_volume"].astype(int)
            social_can_extend = False

    gateway_summary = None
    if social_points.empty and gateway_detail:
        gateway_frame = _stocktwits_gateway_rows(gateway_detail)
        gateway_label = {
            "1D": "1D",
            "1W": "1W",
            "1M": "1M",
            "3M": "3M",
            "6M": "6M",
            "YTD": "1Y",
            "1Y": "1Y",
            "5Y": "ALL",
            "All": "ALL",
        }.get(stocktwits_range_label, "1D")
        gateway_selected = gateway_frame[gateway_frame["timeframe"].astype(str) == gateway_label].copy()
        if gateway_selected.empty:
            gateway_selected = gateway_frame.head(1).copy()
        if not gateway_selected.empty:
            row = gateway_selected.iloc[0]
            gateway_summary = {
                "window": str(row["timeframe"]),
                "message_score": row["message_score_num"],
                "message_value": row["message_value_num"],
                "sentiment_score": row["sentiment_score_num"],
                "sentiment_value": row["sentiment_value_num"],
            }

    price_series = pd.concat(
        [
            work[["datetime", "close"]],
            live_for_chart[["datetime", "close"]],
        ],
        ignore_index=True,
    )
    price_series = (
        price_series.dropna(subset=["datetime", "close"])
        .sort_values("datetime")
        .drop_duplicates(subset=["datetime"], keep="last")
    )
    latest_social_at = pd.NaT
    social_signal_points = social_points.copy()
    if not social_points.empty and "bucket_dt" in social_points.columns:
        latest_social_at = pd.to_datetime(social_points["bucket_dt"], errors="coerce", utc=True).dropna().max()
    if social_can_extend and not social_points.empty and "bucket_dt" in social_points.columns and not price_series.empty:
        social_points = social_points.copy()
        social_points["bucket_dt"] = pd.to_datetime(social_points["bucket_dt"], errors="coerce", utc=True)
        social_points = social_points.dropna(subset=["bucket_dt"]).sort_values("bucket_dt")
        latest_price_dt = price_series["datetime"].max()
        latest_social_dt = social_points["bucket_dt"].max()
        if pd.notna(latest_price_dt) and pd.notna(latest_social_dt) and latest_price_dt > latest_social_dt:
            last_social = social_points.tail(1).copy()
            last_social["bucket_dt"] = latest_price_dt
            social_points = pd.concat([social_points, last_social], ignore_index=True)
            social_points = social_points.drop_duplicates(subset=["bucket_dt"], keep="last")
    historical_step = _median_timedelta(work["datetime"], fallback_minutes=1 if stocktwits_range_label == "1D" else 30)
    max_plot_gap = max(historical_step * 3, pd.Timedelta(minutes=8 if stocktwits_range_label == "1D" else 90))
    plot_price_series = price_series.copy()
    plot_social_points = social_points.copy()

    price_series["display_datetime"] = _to_display_time(price_series["datetime"])
    plot_price_series["display_datetime"] = _to_display_time(plot_price_series["datetime"])
    work["display_datetime"] = _to_display_time(work["datetime"])
    if not social_points.empty and "bucket_dt" in social_points.columns:
        social_points["display_bucket_dt"] = _to_display_time(social_points["bucket_dt"])
    if not plot_social_points.empty and "bucket_dt" in plot_social_points.columns:
        plot_social_points["display_bucket_dt"] = _to_display_time(plot_social_points["bucket_dt"])
    price_min = float(price_series["close"].min())
    price_max = float(price_series["close"].max())
    price_span = max(price_max - price_min, price_max * 0.08, 0.01)
    y_min = max(0.0, price_min - price_span * 0.35)
    y_max = price_max + price_span * 0.25
    volume_height = (work["volume"] / max(float(work["volume"].max()), 1.0)) * ((y_max - y_min) * 0.23)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=plot_price_series["display_datetime"],
            y=plot_price_series["close"],
            name=f"{chart_ticker.upper()} price",
            mode="lines",
            line=dict(color="#00a878", width=2.4),
            connectgaps=True,
            hovertemplate="%{x|%Y-%m-%d %H:%M} ET<br>Price: $%{y:.4f}<extra></extra>",
        ),
        secondary_y=False,
    )

    last = price_series.dropna(subset=["close"]).tail(1)
    if not last.empty:
        last_x = last["display_datetime"].iloc[0]
        last_y = float(last["close"].iloc[0])
        fig.add_annotation(
            x=last_x,
            y=last_y,
            text=f"${last_y:.2f}",
            showarrow=False,
            xanchor="left",
            xshift=8,
            bgcolor="#00a878",
            bordercolor="#00a878",
            borderpad=4,
            font=dict(color="#ffffff", size=12),
        )

    fig.add_bar(
        x=work["display_datetime"],
        y=volume_height,
        base=[y_min] * len(work),
        name="Volume",
        marker_color=work["bar_color"],
        opacity=0.62,
        customdata=work[["volume"]],
        hovertemplate="%{x|%Y-%m-%d %H:%M} ET<br>Volume: %{customdata[0]:,}<extra></extra>",
        secondary_y=False,
    )

    if not social_points.empty:
        if "message_volume" in social_points.columns:
            _message_check = pd.to_numeric(social_points["message_volume"], errors="coerce")
        else:
            _message_check = pd.to_numeric(social_points["message_volume_score"], errors="coerce")
        _sentiment_check = pd.to_numeric(social_points["sentiment_score"], errors="coerce")
        has_message_trend = _message_check.notna().any() and float(_message_check.fillna(0).max()) > 0
        has_sentiment_trend = _sentiment_check.notna().any()
        if not has_message_trend and not has_sentiment_trend:
            social_points = pd.DataFrame()

    if not social_points.empty:
        if "message_volume" in social_points.columns:
            msg_values = social_points["message_volume"]
            plot_msg_values = pd.to_numeric(plot_social_points["message_volume"], errors="coerce")
            msg_label = "Message volume"
        else:
            msg_values = social_points["message_volume_score"]
            plot_msg_values = pd.to_numeric(plot_social_points["message_volume_score"], errors="coerce")
            msg_label = "Message volume score"
        msg_values = pd.to_numeric(msg_values, errors="coerce").fillna(0)
        plot_msg_values = plot_msg_values.fillna(0)
        if msg_values.max() > 100:
            max_messages = max(float(msg_values.max()), 1.0)
            msg_y = (plot_msg_values / max_messages) * 100.0
        else:
            msg_y = plot_msg_values
        if float(msg_values.max()) > 0:
            fig.add_trace(
                go.Scatter(
                    x=plot_social_points["display_bucket_dt"],
                    y=msg_y,
                    name="Message Volume",
                    mode="lines+markers",
                    line=dict(color="#2563eb", width=2.5),
                    marker=dict(size=4, color="#2563eb"),
                    customdata=plot_msg_values,
                    connectgaps=True,
                    hovertemplate="%{x|%Y-%m-%d %H:%M} ET<br>"
                    + msg_label
                    + ": %{customdata:.1f}<extra></extra>",
                ),
                secondary_y=True,
            )
        sentiment_values = pd.to_numeric(social_points["sentiment_score"], errors="coerce")
        plot_sentiment_values = pd.to_numeric(plot_social_points["sentiment_score"], errors="coerce")
        if sentiment_values.notna().any():
            fig.add_trace(
                go.Scatter(
                    x=plot_social_points["display_bucket_dt"],
                    y=plot_sentiment_values,
                    name="Sentiment",
                    mode="lines",
                    line=dict(color="#7c3aed", width=2.2),
                    connectgaps=True,
                    hovertemplate="%{x|%Y-%m-%d %H:%M} ET<br>Sentiment: %{y:.1f}<extra></extra>",
                ),
                secondary_y=True,
            )

    fig.update_layout(
        title=f"{chart_ticker.upper()} price and volume ({stocktwits_range_label})",
        height=540,
        margin=dict(l=36, r=36, t=64, b=42),
        hovermode="x unified",
        dragmode="pan" if chart_interaction_mode == "Pan" else "zoom",
        uirevision=f"{chart_ticker.upper()}-{stocktwits_range_label}",
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
    )
    span_days = max((pd.Timestamp(window_end) - pd.Timestamp(window_start)).days, 0)
    x_tickformat = "%H:%M" if chart_unit == "hourly" and span_days <= 1 else "%m/%d"
    xaxis_range = None
    xaxis_rangebreaks = None
    now_et_naive = datetime.now(DISPLAY_TZ).replace(tzinfo=None)
    if stocktwits_range_label == "1D":
        display_times = price_series["display_datetime"].dropna()
        latest_display_dt = display_times.max() if not display_times.empty else now_et_naive
        today_start = now_et_naive.replace(hour=0, minute=0, second=0, microsecond=0)
        if latest_display_dt.date() == now_et_naive.date():
            session_start = today_start
            session_end = max(now_et_naive, latest_display_dt)
        else:
            session_start = latest_display_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            session_end = latest_display_dt
        session_end = min(session_end + pd.Timedelta(minutes=5), session_start + pd.Timedelta(days=1))
        xaxis_range = [session_start, session_end]
        x_tickformat = "%H:%M"
    elif stocktwits_range_label == "1W":
        xaxis_rangebreaks = [
            dict(bounds=["sat", "mon"]),
            dict(pattern="hour", bounds=[20, 4]),
        ]
        x_tickformat = "%m/%d"
    fig.update_xaxes(
        showgrid=False,
        tickformat=x_tickformat,
        range=xaxis_range,
        rangebreaks=xaxis_rangebreaks,
    )
    fig.update_yaxes(
        title_text="Price",
        tickprefix="$",
        showgrid=True,
        gridcolor="#edf1f5",
        range=[y_min, y_max],
        secondary_y=False,
    )
    fig.update_yaxes(
        title_text="Social score",
        showgrid=False,
        range=[0, 100],
        visible=not social_points.empty,
        secondary_y=True,
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "scrollZoom": True,
            "displayModeBar": True,
            "displaylogo": False,
            "modeBarButtonsToAdd": ["pan2d", "zoom2d", "resetScale2d"],
        },
    )
    if live_merge_note:
        st.warning(live_merge_note)
    render_chart_correlation(work, social_points, chart_ticker=chart_ticker)

    latest_chart_at = work["datetime"].max()
    latest_quote_at = realtime_quotes["datetime"].max() if not realtime_quotes.empty else pd.NaT
    st.subheader("Data freshness")
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Chart latest", _format_display_time(latest_chart_at))
    f2.metric("WebSocket checked", _format_display_time(realtime_checked_at))
    f3.metric("Live quote latest", _format_display_time(latest_quote_at))
    f4.metric("Social latest", _format_display_time(latest_social_at))

    realtime_alerts: list[str] = []
    chart_alerts: list[str] = []
    social_alerts: list[str] = []
    realtime_is_fresh = False
    if pd.notna(latest_quote_at):
        quote_age_seconds = (
            pd.Timestamp(realtime_checked_at).tz_convert("UTC")
            - pd.Timestamp(latest_quote_at).tz_convert("UTC")
        ).total_seconds()
        realtime_is_fresh = quote_age_seconds <= 180
    if realtime_is_fresh and not realtime_quotes.empty:
        live_close = pd.to_numeric(realtime_quotes["close"], errors="coerce").dropna()
        if len(live_close) >= 2:
            live_change = (float(live_close.iloc[-1]) / float(live_close.iloc[0]) - 1.0) * 100.0
            if live_change >= realtime_move_threshold:
                realtime_alerts.append(f"Realtime price moved up {live_change:.1f}% since this app started listening.")
            elif live_change <= -realtime_move_threshold:
                realtime_alerts.append(f"Realtime price moved down {live_change:.1f}% since this app started listening.")
        else:
            realtime_alerts.append("Realtime WebSocket quote is connected, but only one live point is available so far.")
    else:
        latest_close = pd.to_numeric(price_series["close"], errors="coerce").dropna()
        if len(latest_close) >= 5:
            recent_change = (float(latest_close.iloc[-1]) / float(latest_close.iloc[-5]) - 1.0) * 100.0
            if recent_change >= chart_move_threshold:
                chart_alerts.append(f"Chart-window price moved up {recent_change:.1f}% over the latest 5 chart points.")
            elif recent_change <= -chart_move_threshold:
                chart_alerts.append(f"Chart-window price moved down {recent_change:.1f}% over the latest 5 chart points.")
    latest_volume = pd.to_numeric(work["volume"], errors="coerce").fillna(0)
    nonzero_volume = latest_volume[latest_volume > 0]
    if len(nonzero_volume) >= 5:
        recent_volume = float(nonzero_volume.iloc[-1])
        median_volume = float(nonzero_volume.tail(20).median())
        if median_volume > 0 and recent_volume >= median_volume * volume_spike_multiple:
            chart_alerts.append(f"Chart-window volume spike: latest bar is {recent_volume / median_volume:.1f}x recent median.")
    if not social_signal_points.empty:
        latest_msg = (
            pd.to_numeric(social_signal_points["message_volume_score"], errors="coerce").dropna()
            if "message_volume_score" in social_signal_points.columns
            else pd.Series(dtype="float64")
        )
        latest_sent = (
            pd.to_numeric(social_signal_points["sentiment_score"], errors="coerce").dropna()
            if "sentiment_score" in social_signal_points.columns
            else pd.Series(dtype="float64")
        )
        if not latest_msg.empty and float(latest_msg.iloc[-1]) >= message_volume_threshold:
            social_alerts.append("Latest Stocktwits message-volume score is very high.")
        if not latest_sent.empty:
            sent_last = float(latest_sent.iloc[-1])
            if sent_last >= bullish_sentiment_threshold:
                social_alerts.append("Latest Stocktwits sentiment is strongly bullish.")
            elif sent_last <= bearish_sentiment_threshold:
                social_alerts.append("Latest Stocktwits sentiment is strongly bearish.")
    st.subheader("Alerts")
    alert_lines = []
    alert_lines.extend(f"[Realtime] {item}" for item in realtime_alerts)
    alert_lines.extend(f"[Chart window] {item}" for item in chart_alerts)
    alert_lines.extend(f"[Social latest] {item}" for item in social_alerts)
    if realtime_alerts or chart_alerts or social_alerts:
        st.warning("\n".join(f"- {item}" for item in alert_lines))
    else:
        st.success("No realtime or chart-window alert triggers.")
    render_alert_history(chart_ticker, stocktwits_range_label, alert_lines)
    if not realtime_is_fresh:
        st.caption(
            "Realtime alert note: no fresh WebSocket quote was available within 3 minutes of the latest check, "
            "so price/volume alerts use the Stocktwits chart window instead."
        )

    if social_points.empty:
        if gateway_summary:
            msg_value = gateway_summary["message_value"]
            msg_score = gateway_summary["message_score"]
            sent_value = gateway_summary["sentiment_value"]
            sent_score = gateway_summary["sentiment_score"]
            st.caption(
                "No parsed Stocktwits post history was available for this refresh, so sentiment/message volume are not "
                f"drawn as trend lines. Gateway snapshot for {gateway_summary['window']}: "
                f"message volume {('N/A' if pd.isna(msg_value) else f'{int(msg_value):,}')} "
                f"(score {('N/A' if pd.isna(msg_score) else f'{float(msg_score):.1f}')}), "
                f"sentiment {('N/A' if pd.isna(sent_value) else f'{float(sent_value):.3f}')} "
                f"(score {('N/A' if pd.isna(sent_score) else f'{float(sent_score):.1f}')})."
            )
        else:
            st.caption("No parsed Stocktwits post history was available for this refresh.")
    else:
        if social_can_extend:
            st.caption(
                f"Price and stock volume are drawn from {chart_source}. "
                "Sentiment and message-volume lines extend the latest Stocktwits social score until a newer score arrives."
            )
        else:
            st.caption(
                f"Price and stock volume are drawn from {chart_source}. "
                "Sentiment and message-volume points are computed only from parsed Stocktwits posts in the visible chart range."
            )
        if not realtime_quotes.empty:
            latest_quote_at = realtime_quotes["datetime"].max()
            st.caption(
                "Realtime status: "
                f"WebSocket checked {_format_display_time(realtime_checked_at)}; "
                f"latest Stocktwits quote timestamp {_format_display_time(latest_quote_at)}."
            )
        elif realtime_err:
            st.caption(f"Realtime status: WebSocket checked, but no live quote was returned ({realtime_err}).")


def _stocktwits_sentiment_summary(messages: pd.DataFrame) -> dict[str, object]:
    if messages.empty:
        return {
            "score": 50,
            "label": "No signal",
            "avg_compound": None,
            "positive": 0,
            "neutral": 0,
            "negative": 0,
            "count": 0,
        }

    scored = analyze_dataframe(messages, engine=LIVE_SCORE_ENGINE)
    avg_compound = float(scored["sentiment_compound"].mean()) if not scored.empty else 0.0
    score = round((avg_compound + 1.0) * 50)
    score = max(0, min(100, score))
    if score >= 80:
        label = "Extremely Bullish"
    elif score >= 60:
        label = "Bullish"
    elif score > 40:
        label = "Neutral"
    elif score > 20:
        label = "Bearish"
    else:
        label = "Extremely Bearish"
    label_counts = scored["sentiment_label"].value_counts()
    return {
        "score": score,
        "label": label,
        "avg_compound": avg_compound,
        "positive": int(label_counts.get("positive", 0)),
        "neutral": int(label_counts.get("neutral", 0)),
        "negative": int(label_counts.get("negative", 0)),
        "count": len(scored),
    }


def _message_volume_summary(messages: pd.DataFrame, social_metrics: pd.DataFrame, chart_ticker: str) -> dict[str, object]:
    count = int(len(messages))
    peer_max = count
    if not social_metrics.empty and "social_count" in social_metrics.columns:
        peer_max = int(social_metrics["social_count"].fillna(0).max())
    score = round((count / peer_max) * 100) if peer_max > 0 else 0
    score = max(0, min(100, score))
    if score >= 80:
        label = "Extremely High"
    elif score >= 60:
        label = "High"
    elif score >= 30:
        label = "Moderate"
    elif score > 0:
        label = "Low"
    else:
        label = "No volume"
    return {
        "score": score,
        "label": label,
        "count": count,
        "peer_max": peer_max,
        "ticker": chart_ticker.upper(),
    }


def _gauge_figure(score: int, title: str, label: str, color: str) -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "", "font": {"size": 28}},
            title={"text": f"<b>{title}</b><br><span style='font-size:14px'>{label}</span>", "font": {"size": 15}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 0, "showticklabels": False},
                "bar": {"color": color, "thickness": 0.24},
                "bgcolor": "#f0f2f5",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 40], "color": "#eef1f5"},
                    {"range": [40, 70], "color": "#e4e9ef"},
                    {"range": [70, 100], "color": "#d9e1e9"},
                ],
            },
        )
    )
    fig.update_layout(height=130, margin=dict(l=10, r=10, t=35, b=5))
    return fig


def _corr_label(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    value = float(value)
    strength = "weak"
    if abs(value) >= 0.7:
        strength = "strong"
    elif abs(value) >= 0.4:
        strength = "moderate"
    direction = "positive" if value >= 0 else "negative"
    return f"{value:.2f} ({strength} {direction})"


def render_chart_correlation(
    price_bars: pd.DataFrame,
    social_points: pd.DataFrame,
    *,
    chart_ticker: str,
) -> None:
    """Show quick correlation checks between price movement, volume, and social signals."""
    st.subheader("Correlation analysis")
    if price_bars.empty or len(price_bars) < 4:
        st.caption("Not enough chart bars for correlation analysis yet.")
        return

    frame = price_bars[["datetime", "close", "volume"]].copy()
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce", utc=True)
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0)
    frame = frame.dropna(subset=["datetime", "close"]).sort_values("datetime")
    frame["price_change_pct"] = frame["close"].pct_change() * 100.0

    rows: list[dict[str, object]] = []
    base = frame.dropna(subset=["price_change_pct"])
    if len(base) >= 4 and base["volume"].nunique(dropna=True) > 1:
        rows.append(
            {
                "relationship": "Price change vs stock volume",
                "points": len(base),
                "correlation": base["price_change_pct"].corr(base["volume"]),
                "source": "Stocktwits chart",
            }
        )

    if not social_points.empty and "bucket_dt" in social_points.columns:
        social = social_points.copy()
        social["bucket_dt"] = pd.to_datetime(social["bucket_dt"], errors="coerce", utc=True)
        social = social.dropna(subset=["bucket_dt"]).sort_values("bucket_dt")
        if "message_volume" in social.columns:
            social["message_value"] = pd.to_numeric(social["message_volume"], errors="coerce")
        elif "message_volume_score" in social.columns:
            social["message_value"] = pd.to_numeric(social["message_volume_score"], errors="coerce")
        else:
            social["message_value"] = pd.NA
        social["sentiment_value"] = pd.to_numeric(social.get("sentiment_score"), errors="coerce")
        aligned = pd.merge_asof(
            frame.sort_values("datetime"),
            social[["bucket_dt", "message_value", "sentiment_value"]].sort_values("bucket_dt"),
            left_on="datetime",
            right_on="bucket_dt",
            direction="backward",
        )
        aligned = aligned.dropna(subset=["price_change_pct"])
        msg_aligned = aligned.dropna(subset=["message_value"])
        if len(msg_aligned) >= 4 and msg_aligned["message_value"].nunique(dropna=True) > 1:
            rows.append(
                {
                    "relationship": "Price change vs message volume",
                    "points": len(msg_aligned),
                    "correlation": msg_aligned["price_change_pct"].corr(msg_aligned["message_value"]),
                    "source": "Stocktwits social",
                }
            )
        sent_aligned = aligned.dropna(subset=["sentiment_value"])
        if len(sent_aligned) >= 4 and sent_aligned["sentiment_value"].nunique(dropna=True) > 1:
            rows.append(
                {
                    "relationship": "Price change vs sentiment",
                    "points": len(sent_aligned),
                    "correlation": sent_aligned["price_change_pct"].corr(sent_aligned["sentiment_value"]),
                    "source": "Stocktwits social",
                }
            )

    if not rows:
        st.caption(
            f"{chart_ticker.upper()} does not have enough varying social/volume points in this chart window "
            "to compute a meaningful correlation yet."
        )
        return

    result = pd.DataFrame(rows)
    result["correlation"] = pd.to_numeric(result["correlation"], errors="coerce")
    result["interpretation"] = result["correlation"].map(_corr_label)
    st.dataframe(
        result[["relationship", "points", "interpretation", "source"]],
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "Correlation is calculated inside the visible Stocktwits chart window. It is a quick signal check, "
        "not a trading recommendation."
    )


def _record_alert_history(ticker: str, range_label: str, alert_lines: list[str]) -> pd.DataFrame:
    history = st.session_state.get("stocktwits_alert_history")
    if not isinstance(history, list):
        history = []
    now_text = datetime.now(DISPLAY_TZ).strftime(f"%Y-%m-%d %H:%M:%S {DISPLAY_TZ_LABEL}")
    seen = {(row.get("ticker"), row.get("range"), row.get("alert")) for row in history}
    for alert in alert_lines:
        key = (ticker.upper(), range_label, alert)
        if key in seen:
            continue
        history.append(
            {
                "first_seen": now_text,
                "ticker": ticker.upper(),
                "range": range_label,
                "alert": alert,
            }
        )
    history = history[-100:]
    st.session_state["stocktwits_alert_history"] = history
    return pd.DataFrame(history)


def render_alert_history(ticker: str, range_label: str, alert_lines: list[str]) -> None:
    history = _record_alert_history(ticker, range_label, alert_lines)
    with st.expander("Alert history and export", expanded=False):
        if history.empty:
            st.caption("No alerts have been recorded during this app session yet.")
            return
        st.dataframe(history.iloc[::-1], width="stretch", hide_index=True)
        st.download_button(
            "Download alert log CSV",
            history.to_csv(index=False).encode("utf-8"),
            file_name=f"stocktwits_alert_log_{ticker.upper()}.csv",
            mime="text/csv",
        )


def render_stocktwits_signal_cards(
    messages: pd.DataFrame,
    *,
    social_metrics: pd.DataFrame,
    chart_ticker: str,
) -> None:
    st.subheader("Computed Stocktwits signals")
    sentiment = _stocktwits_sentiment_summary(messages)
    volume = _message_volume_summary(messages, social_metrics, chart_ticker)
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            _gauge_figure(int(sentiment["score"]), "Sentiment", str(sentiment["label"]), "#089981"),
            use_container_width=True,
        )
        avg_text = "N/A" if sentiment["avg_compound"] is None else f"{sentiment['avg_compound']:.3f}"
        st.caption(
            f"Our VADER score from {sentiment['count']} fetched posts. "
            f"Positive {sentiment['positive']} / Neutral {sentiment['neutral']} / Negative {sentiment['negative']}; "
            f"avg compound {avg_text}."
        )
    with c2:
        st.plotly_chart(
            _gauge_figure(int(volume["score"]), "Message Volume", str(volume["label"]), "#089981"),
            use_container_width=True,
        )
        st.caption(
            f"{volume['ticker']} has {volume['count']} fetched posts in this window. "
            f"Volume score is relative to the highest fetched ticker count ({volume['peer_max']})."
        )


def render_social_tab(
    tickers: list[str],
    *,
    chart_ticker: str,
    token: str,
    fetch_enabled: bool,
    window_start,
    window_end,
    window_label: str,
    time_start: datetime_time,
    time_end: datetime_time,
    time_label: str,
    chart_unit: str,
    stocktwits_range_label: str,
    chart_interaction_mode: str,
    alert_settings: dict[str, float],
) -> None:
    """Self-contained social panel, separate from Finviz tabs and metrics."""
    st.subheader("Stocktwits rolling window")
    st.caption(
        "Social sourcing via **Stocktwits** by default; **not connected to Finviz** news, K-line, or ranked table. "
        "The rolling window in this tab filters Stocktwits messages only."
    )
    st.write(f"Stocktwits chart range: **{stocktwits_range_label}**")
    chart_window_slot = st.empty()
    chart_window_slot.write("Chart actual window: **loading from Stocktwits...**")
    st.write(f"Parsed message filter: **{window_label}**, **{time_label}**")
    unit_label = {"monthly": "Month", "daily": "Day", "hourly": "Hour"}.get(chart_unit, chart_unit)
    st.write(f"Chart unit: **{unit_label}**")
    st.write(f"Chart ticker: **{chart_ticker.upper()}**")
    st.info(
        "Data source note: price, stock volume, sentiment, and message-volume are drawn from Stocktwits chart data "
        "when available; the latest price can be extended by the Stocktwits WebSocket quote stream. This chart does "
        "not use local demo snapshots."
    )

    if not fetch_enabled:
        st.info(
            "Social fetch is **off** (default). Check **Enable social fetch** in the sidebar "
            "Social section, then click **Refresh social** if needed."
        )
        return

    social_fetch_tickers = list(dict.fromkeys([chart_ticker.upper(), *tickers]))
    social_messages, social_errs = load_live_social(tuple(social_fetch_tickers))
    social_metrics, social_date_filtered = build_social_metrics(
        social_messages,
        tickers,
        window_start=window_start,
        window_end=window_end,
    )
    social_filtered = filter_messages_by_time_window(
        social_date_filtered,
        time_start=time_start,
        time_end=time_end,
    )
    social_metrics, _ = build_social_metrics(social_filtered, tickers)

    raw_count = len(social_messages)
    date_count = len(social_date_filtered)
    time_count = len(social_filtered)
    fetched_tickers = (
        social_messages["ticker"].astype(str).str.upper().nunique()
        if not social_messages.empty and "ticker" in social_messages.columns
        else 0
    )
    coverage_note = ""
    active_months_note = ""
    if not social_messages.empty and "published" in social_messages.columns:
        fetched_dt = pd.to_datetime(social_messages["published"], errors="coerce", utc=True).dropna()
        if not fetched_dt.empty:
            coverage_note = (
                f" Fetched message dates: **{fetched_dt.min().date()} -> {fetched_dt.max().date()}**."
            )
    if chart_unit == "monthly" and not social_filtered.empty and "published" in social_filtered.columns:
        filtered_dt = pd.to_datetime(social_filtered["published"], errors="coerce", utc=True).dropna()
        if not filtered_dt.empty:
            active_months = ", ".join(sorted(filtered_dt.dt.strftime("%Y-%m").unique()))
            active_months_note = f" Months with fetched messages: **{active_months}**."
    st.caption(
        f"Stocktwits web/curl-impersonate fetch: **{raw_count}** recent messages from **{fetched_tickers}** fetched tickers; "
        f"after date window: **{date_count}**; after time window: **{time_count}**. "
        "This is not a full six-month historical backfill."
        f"{coverage_note}{active_months_note}"
    )

    if social_errs:
        st.warning("Social fetch notes: " + "; ".join(social_errs[:3]))

    using_sample = (
        not social_messages.empty
        and "source" in social_messages.columns
        and social_messages["source"].astype(str).str.contains("sample", case=False).any()
    )
    if using_sample:
        st.info(
            "Sample social posts are enabled for this run. Disable SOCIAL_ALLOW_SAMPLE/STOCKTWITS_ALLOW_SAMPLE "
            "for a live-only presentation."
        )

    chart_messages = social_filtered[
        social_filtered["ticker"].astype(str).str.upper() == chart_ticker.upper()
    ] if not social_filtered.empty and "ticker" in social_filtered.columns else social_filtered

    gateway_detail, gateway_err = load_stocktwits_sentiment_detail(chart_ticker.upper())
    if gateway_err:
        st.warning(f"Stocktwits sentiment gateway note: {gateway_err}")

    render_stocktwits_style_market_chart(
        chart_ticker=chart_ticker,
        token=token,
        messages=chart_messages,
        gateway_detail=None if gateway_err else gateway_detail,
        window_start=window_start,
        window_end=window_end,
        window_label=window_label,
        time_label=time_label,
        chart_unit=chart_unit,
        stocktwits_range_label=stocktwits_range_label,
        chart_interaction_mode=chart_interaction_mode,
        realtime_move_threshold=alert_settings["realtime_move_threshold"],
        chart_move_threshold=alert_settings["chart_move_threshold"],
        volume_spike_multiple=alert_settings["volume_spike_multiple"],
        message_volume_threshold=alert_settings["message_volume_threshold"],
        bullish_sentiment_threshold=alert_settings["bullish_sentiment_threshold"],
        bearish_sentiment_threshold=alert_settings["bearish_sentiment_threshold"],
        chart_window_slot=chart_window_slot,
    )

    total = int(social_metrics["social_count"].fillna(0).sum()) if not social_metrics.empty else 0
    if total <= 0:
        st.caption(
            "Parsed Stocktwits message-feed rows are unavailable for this refresh; "
            "the official Stocktwits gateway metrics above are the primary data source."
        )
        return

    m_total, m_ticker = st.columns(2)
    m_total.metric(f"Parsed web messages ({window_label}, {time_label})", total)
    m_ticker.metric(f"{chart_ticker.upper()} parsed messages", len(chart_messages))

    message_flags = build_message_keyword_flags(social_filtered)
    flagged_messages = message_flags[message_flags["keyword_hits"] > 0] if not message_flags.empty else message_flags
    if not flagged_messages.empty:
        with st.expander("Social keyword and gossip detection", expanded=False):
            summary = (
                message_flags.groupby("ticker", as_index=False)
                .agg(
                    keyword_posts=("keyword_hits", lambda s: int((s > 0).sum())),
                    gossip_posts=("gossip_hits", "sum"),
                    squeeze_posts=("squeeze_hits", "sum"),
                    risk_posts=("risk_hits", "sum"),
                )
                .sort_values(["keyword_posts", "ticker"], ascending=[False, True])
            )
            st.dataframe(summary.head(20), width="stretch", hide_index=True)
            watch_cols = [
                c
                for c in ("ticker", "title", "top_keyword_group", "keyword_hits", "gossip_hits", "squeeze_hits", "published", "url")
                if c in flagged_messages.columns
            ]
            st.dataframe(flagged_messages[watch_cols].head(50), width="stretch", hide_index=True)
            st.download_button(
                "Download social keyword hits CSV",
                flagged_messages.to_csv(index=False).encode("utf-8"),
                file_name="stocktwits_keyword_gossip_hits.csv",
                mime="text/csv",
                width="stretch",
            )

    if chart_messages.empty:
        st.info(
            "No parsed Stocktwits message-feed rows for this ticker/window. "
            "Use the Stocktwits gateway chart above for the real sentiment and message-volume metrics."
        )
    else:
        with st.expander("Computed Stocktwits message-volume detail", expanded=False):
            render_stocktwits_volume_chart(
                chart_messages,
                chart_ticker=chart_ticker,
                token=token,
                window_label=window_label,
                time_label=time_label,
                chart_unit=chart_unit,
                window_start=window_start,
                window_end=window_end,
            )

    has_message_counts = (
        not social_metrics.empty
        and "social_count" in social_metrics.columns
        and int(social_metrics["social_count"].fillna(0).sum()) > 0
    )
    if has_message_counts:
        st.subheader("Per-ticker counts")
        show_cols = [c for c in ("ticker", "social_count", "social_density") if c in social_metrics.columns]
        view = social_metrics[show_cols].copy().sort_values(
            ["social_count", "ticker"],
            ascending=[False, True],
        )
        if "social_density" in view.columns:
            view["social_density"] = view["social_density"].map(_format_density_label)
        if "social_count" in view.columns and view["social_count"].max() >= 30:
            st.caption(
                "Note: counts of exactly 30 often reflect the parsed Stocktwits web message page size "
                "for a symbol, not the full platform-wide message total."
            )
        st.dataframe(view, width="stretch", hide_index=True)

    st.subheader("Messages")
    if social_filtered.empty:
        st.info("No parsed Stocktwits message-feed rows in this date range.")
        return

    available = sorted(social_filtered["ticker"].astype(str).str.upper().unique())
    selected = st.selectbox("Select ticker", available, key="live_social_ticker")
    cols = [
        c
        for c in ("title", "summary", "social_sentiment", "published", "url", "source")
        if c in social_filtered.columns
    ]
    ticker_msgs = social_filtered[social_filtered["ticker"].astype(str).str.upper() == selected][cols]
    st.write(f"**{len(ticker_msgs)}** messages for **{selected}**")
    st.dataframe(ticker_msgs, width="stretch", hide_index=True)


def main() -> None:
    st.set_page_config(page_title="Fin News Sentiment", layout="wide")
    st.title("Financial News Sentiment Dashboard")

    pipeline_engine = read_engine_metadata(ENGINE_META)
    eval_report = PROJECT_ROOT / "data" / "processed" / "sentiment_eval_report.csv"
    st.caption(
        f"IST 495 - **Live Finviz** - live scoring **{LIVE_SCORE_ENGINE.upper()}** - auto-refresh 60s"
    )
    if pipeline_engine != LIVE_SCORE_ENGINE:
        st.caption(
            f"Pipeline last used **{pipeline_engine.upper()}** "
            f"(see `data/processed/sentiment_eval_report.csv` for model comparison)."
        )
    elif eval_report.exists():
        st.caption("FinBERT evaluation: `data/processed/sentiment_eval_report.csv`")

    try:
        token = get_api_token()
    except RuntimeError as exc:
        st.error(str(exc))
        return

    st.sidebar.caption(
        f"Finviz token from `.env`: `{token[:4]}...` "
        f"(compare with [Settings ->API](https://elite.finviz.com/api_explanation))"
    )

    try:
        live_screener = load_live_screener(token)
        st.session_state["last_live_screener"] = live_screener
    except Exception as exc:  # noqa: BLE001
        cached_screener = st.session_state.get("last_live_screener")
        if isinstance(cached_screener, pd.DataFrame) and not cached_screener.empty:
            live_screener = cached_screener
            st.warning(
                "Live Finviz screener is temporarily rate-limited; using the last loaded screener rows. "
                f"Details: {_safe_error_text(exc)}"
            )
        else:
            live_screener = fallback_screener()
            st.warning(
                "Live Finviz screener is temporarily rate-limited and no cached screener is available. "
                "Using a small fallback ticker list so the dashboard can keep running. "
                f"Details: {_safe_error_text(exc)}"
            )
            auth_help = _finviz_auth_help(exc)
            if auth_help:
                st.info(auth_help)

    tickers = live_screener["ticker"].astype(str).str.upper().tolist()
    today = utc_today()

    with st.sidebar:
        st.header("Finviz filters")
        st.subheader("News date range")
        news_range_preset = st.radio(
            "Quick range",
            ["Last 7 days", "Last 30 days", "Last 6 months", "All on page", "Custom"],
            index=0,
            help="Filter live Finviz news_count and News viewer by published date.",
        )
        default_start = today - timedelta(days=6)
        if news_range_preset == "Custom":
            custom_start = st.date_input("From", value=default_start, max_value=today)
            custom_end = st.date_input("To", value=today, max_value=today)
        else:
            custom_start = default_start
            custom_end = today

        window_start, window_end, window_label = resolve_news_window_preset(
            news_range_preset,
            custom_start=custom_start,
            custom_end=custom_end,
        )
        if news_range_preset != "Custom":
            st.caption(f"Using **{window_label}** (UTC)")

        sectors = ["All"]
        if "sector" in live_screener.columns:
            sectors += sorted(s for s in live_screener["sector"].dropna().unique() if str(s).strip())
        sector_filter = st.selectbox("Sector", sectors)
        min_news = st.slider("Minimum news count (in range)", 0, 20, 0)
        sort_by = st.selectbox(
            "Sort by",
            ["screener_rank", "change_pct", "volume", "news_count", "sentiment_rank", "message_density"],
            index=0,
        )
        sort_asc = st.checkbox("Ascending", value=False)

        st.divider()
        st.header("Live Finviz chart")
        chart_ticker = st.selectbox("Chart ticker", tickers, index=0)
        period_label = st.selectbox(
            "Interval",
            list(PERIOD_OPTIONS.keys()),
            index=list(PERIOD_OPTIONS.keys()).index("D"),
        )
        sma_options = list(available_sma_periods(period_label))
        sma_defaults = [p for p in default_sma_periods(period_label) if p in sma_options]
        selected_smas = st.multiselect(
            "SMA overlays",
            options=sma_options,
            default=sma_defaults,
            format_func=lambda p: f"SMA {p}",
        )
        chart_window_start = None
        chart_window_end = None
        chart_window_label = "all bars"
        enable_chart_window = st.checkbox(
            "Enable Finviz K-line rolling window",
            value=False,
            help="Optional: zoom the Finviz chart by date range. This does not affect Stocktwits.",
        )
        if enable_chart_window:
            st.caption("Finviz K-line rolling window (UTC calendar dates)")
            chart_range_preset = st.radio(
                "K-line quick range",
                ["Last 7 days", "Last 30 days", "Last 6 months", "All on page", "Custom"],
                index=0,
                key="chart_range_preset",
            )
            chart_default_start = today - timedelta(days=6)
            if chart_range_preset == "Custom":
                chart_custom_start = st.date_input(
                    "K-line from",
                    value=chart_default_start,
                    max_value=today,
                    key="chart_from",
                )
                chart_custom_end = st.date_input(
                    "K-line to",
                    value=today,
                    max_value=today,
                    key="chart_to",
                )
            else:
                chart_custom_start = chart_default_start
                chart_custom_end = today
            chart_window_start, chart_window_end, chart_window_label = resolve_news_window_preset(
                chart_range_preset,
                custom_start=chart_custom_start,
                custom_end=chart_custom_end,
            )
            if chart_range_preset != "Custom":
                st.caption(f"K-line window: **{chart_window_label}**")

        auto_refresh = st.checkbox(
            "Auto-refresh screener & chart (60s)",
            value=True,
            help="Refreshes Finviz price/chart every 60s. News cached ~5 min.",
        )
        if st.button("Refresh Finviz"):
            load_live_bars.clear()
            load_live_screener.clear()
            load_live_finviz_scored.clear()
            st.rerun()

        st.divider()
        st.header("Social source")
        st.caption("Optional Stocktwits social posts - separate from Finviz above.")
        fetch_social = st.checkbox(
            "Enable social fetch",
            value=False,
            help="Off by default: avoids extra Stocktwits calls while using Finviz tabs.",
        )
        social_ticker_options = tickers if tickers else [chart_ticker]
        social_ticker_default = chart_ticker if chart_ticker in social_ticker_options else social_ticker_options[0]
        social_chart_ticker = st.selectbox(
            "Social chart ticker",
            social_ticker_options,
            index=social_ticker_options.index(social_ticker_default),
            key="social_chart_ticker",
            help="Uses the same ticker list as the Finviz chart selector.",
        )
        social_chart_ticker = str(social_chart_ticker).strip().upper()
        if not social_chart_ticker:
            social_chart_ticker = chart_ticker
        range_options = ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "5Y", "All"]
        range_default = st.session_state.get("stocktwits_chart_range_inline", "1W")
        if range_default not in range_options:
            range_default = "1W"
        stocktwits_range_label = st.radio(
            "Stocktwits chart range",
            range_options,
            index=range_options.index(range_default),
            horizontal=True,
            key="stocktwits_chart_range_inline",
        )
        if stocktwits_range_label not in ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "5Y", "All"]:
            stocktwits_range_label = "1W"
        if stocktwits_range_label == "1D":
            social_window_start = today
            social_window_end = today
            social_chart_unit = "hourly"
        elif stocktwits_range_label == "1W":
            social_window_start = today - timedelta(days=7)
            social_window_end = today
            social_chart_unit = "hourly"
        elif stocktwits_range_label == "1M":
            social_window_start = subtract_months(today, 1)
            social_window_end = today
            social_chart_unit = "daily"
        elif stocktwits_range_label == "3M":
            social_window_start = subtract_months(today, 3)
            social_window_end = today
            social_chart_unit = "daily"
        elif stocktwits_range_label == "6M":
            social_window_start = subtract_months(today, 6)
            social_window_end = today
            social_chart_unit = "daily"
        elif stocktwits_range_label == "YTD":
            social_window_start = today.replace(month=1, day=1)
            social_window_end = today
            social_chart_unit = "daily"
        elif stocktwits_range_label == "1Y":
            social_window_start = subtract_months(today, 12)
            social_window_end = today
            social_chart_unit = "daily"
        elif stocktwits_range_label == "5Y":
            social_window_start = subtract_months(today, 60)
            social_window_end = today
            social_chart_unit = "daily"
        else:
            social_window_start = subtract_months(today, 240)
            social_window_end = today
            social_chart_unit = "daily"
        social_window_label = f"{social_window_start} -> {social_window_end}"
        social_time_start = datetime_time(0, 0)
        social_time_end = datetime_time(23, 59)
        social_time_label = "All day"
        st.caption(
            f"Requested **{stocktwits_range_label}**: **{social_window_label}**. "
            "The actual Stocktwits chart window is shown above the chart after data loads."
        )
        social_auto_refresh = st.checkbox(
            "Auto-refresh Stocktwits chart (60s)",
            value=True,
            help="Refreshes the Stocktwits price/sentiment/message-volume chart every minute.",
        )
        chart_interaction_mode = st.radio(
            "Chart interaction mode",
            ["Pan", "Zoom"],
            index=0,
            horizontal=True,
            help="Pan lets you hold and drag the chart left/right. Zoom lets you drag a box to zoom in.",
        )
        with st.expander("Alert rule settings", expanded=False):
            realtime_move_threshold = st.slider(
                "Realtime price move %",
                0.5,
                10.0,
                1.5,
                0.5,
                help="Alert when WebSocket price changes by this percent after the app starts listening.",
            )
            chart_move_threshold = st.slider(
                "Chart-window price move %",
                1.0,
                25.0,
                5.0,
                0.5,
                help="Fallback alert based on the latest chart bars when fresh WebSocket quotes are unavailable.",
            )
            volume_spike_multiple = st.slider(
                "Volume spike multiple",
                1.5,
                10.0,
                2.5,
                0.5,
                help="Alert when the latest nonzero volume bar is this many times recent median volume.",
            )
            message_volume_threshold = st.slider(
                "Message-volume score",
                50,
                100,
                90,
                5,
                help="Alert when latest Stocktwits message-volume score reaches this level.",
            )
            bullish_sentiment_threshold = st.slider("Bullish sentiment score", 50, 100, 80, 5)
            bearish_sentiment_threshold = st.slider("Bearish sentiment score", 0, 50, 20, 5)
        alert_settings = {
            "realtime_move_threshold": float(realtime_move_threshold),
            "chart_move_threshold": float(chart_move_threshold),
            "volume_spike_multiple": float(volume_spike_multiple),
            "message_volume_threshold": float(message_volume_threshold),
            "bullish_sentiment_threshold": float(bullish_sentiment_threshold),
            "bearish_sentiment_threshold": float(bearish_sentiment_threshold),
        }
        if st.button("Refresh social"):
            load_live_social.clear()
            load_stocktwits_sentiment_detail.clear()
            load_stocktwits_chart_data.clear()
            load_stocktwits_realtime_quotes.clear()
            st.rerun()

    sma_tuple = tuple(selected_smas) if selected_smas else default_sma_periods(period_label)

    screener = live_screener
    tlist = screener["ticker"].astype(str).str.upper().tolist()
    scored_all, errs = load_live_finviz_scored(tuple(tlist), token, LIVE_SCORE_ENGINE)

    def _render_finviz_dashboard(live_screener: pd.DataFrame) -> None:
        metrics, scored = build_metrics_from_scored(
            scored_all,
            tlist,
            window_start=window_start,
            window_end=window_end,
        )
        if errs:
            st.warning("Some tickers failed live Finviz news fetch: " + "; ".join(errs[:3]))

        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        total_news = int(metrics["news_count"].fillna(0).sum()) if not metrics.empty else 0
        st.caption(f"**Live Finviz fetch:** {fetched_at} - **{total_news}** articles in range ({window_label})")

        merged = merge_live_screener_with_metrics(live_screener, metrics)
        filtered = filter_table(merged, sector_filter, min_news)
        if sort_by in filtered.columns:
            filtered = filtered.sort_values(sort_by, ascending=sort_asc, na_position="last").reset_index(
                drop=True
            )

        m1, m2, m3 = st.columns(3)
        m1.metric("Tickers", len(filtered))
        if "news_count" in filtered.columns:
            m2.metric(f"Finviz news ({window_label})", int(filtered["news_count"].fillna(0).sum()))
        if "change_pct" in filtered.columns:
            m3.metric("Mean change % (live)", f"{filtered['change_pct'].mean():.2f}%")

        tab_chart, tab_table, tab_news, tab_signals, tab_tradingview, tab_social, tab_checklist, tab_export = st.tabs(
            ["Live Finviz chart", "Ranked tickers", "News viewer", "Signals", "TradingView", "Social", "Checklist", "Export"]
        )
        with tab_chart:
            render_live_chart(
                chart_ticker,
                _company_for_ticker(live_screener, chart_ticker),
                period_label,
                token,
                sma_periods=sma_tuple,
                live_screener=live_screener,
                live_news=scored,
                chart_window_start=chart_window_start,
                chart_window_end=chart_window_end,
                chart_window_label=chart_window_label,
                apply_chart_window=enable_chart_window,
            )
        with tab_table:
            render_ranked_table(filtered, window_label=window_label)
        with tab_news:
            render_news_viewer(scored)
        with tab_signals:
            render_signal_scanner(filtered, scored, tlist)
        with tab_tradingview:
            render_tradingview_screener()
        with tab_social:
            render_social_tab(
                tlist,
                chart_ticker=social_chart_ticker,
                token=token,
                fetch_enabled=fetch_social,
                window_start=social_window_start,
                window_end=social_window_end,
                window_label=social_window_label,
                time_start=social_time_start,
                time_end=social_time_end,
                time_label=social_time_label,
                chart_unit=social_chart_unit,
                stocktwits_range_label=stocktwits_range_label,
                chart_interaction_mode=chart_interaction_mode,
                alert_settings=alert_settings,
            )
        with tab_checklist:
            render_professor_checklist()
        with tab_export:
            render_export_report(
                chart_ticker=social_chart_ticker,
                filtered=filtered,
                scored=scored,
                window_label=window_label,
                stocktwits_range_label=stocktwits_range_label,
                alert_settings=alert_settings,
            )

    if auto_refresh or social_auto_refresh:
        @st.fragment(run_every=60)
        def live_dashboard() -> None:
            if social_auto_refresh:
                load_stocktwits_realtime_quotes.clear()
            _render_finviz_dashboard(screener)

        live_dashboard()
    else:
        _render_finviz_dashboard(screener)

    st.caption(f"Loaded {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")


if __name__ == "__main__":
    main()
