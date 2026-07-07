"""
Streamlit dashboard: Finviz live chart + screener table + news viewer.

Ranked tickers and news_count come from **live Finviz quote pages** (60s refresh),
not pipeline CSV snapshots.

Social sourcing lives in its own tab + sidebar section — does not alter Finviz.

Run from repo root:
  streamlit run src/dashboard.py
"""
from __future__ import annotations

import sys
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

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
from src.finviz_config import (
    PRESET_TECHNICAL_GAINERS,
    build_elite_stock_url,
    get_api_token,
)
from src.live_finviz_metrics import (
    build_metrics_from_scored,
    fetch_and_score_live_finviz_news,
    resolve_news_window_preset,
)
from src.live_social_metrics import build_social_metrics, fetch_live_social
from src.news_filters import utc_today
from src.sentiment_engines import read_engine_metadata

ENGINE_META = PROJECT_ROOT / "data" / "processed" / "sentiment_engine.txt"
LIVE_SCORE_ENGINE = "vader"


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


@st.cache_data(ttl=300, show_spinner="Fetching live Finviz news…")
def load_live_finviz_scored(
    tickers: tuple[str, ...],
    token: str,
    engine: str,
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    scored, errors = fetch_and_score_live_finviz_news(list(tickers), token, engine=engine)
    return scored, tuple(errors)


@st.cache_data(ttl=900, show_spinner="Fetching social posts (rate-limited, cached 15 min)…")
def load_live_social(tickers: tuple[str, ...]) -> tuple[pd.DataFrame, tuple[str, ...]]:
    messages, errors = fetch_live_social(list(tickers))
    return messages, tuple(errors)


def merge_live_screener_with_metrics(live: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    out = live
    if not metrics.empty:
        cols = [c for c in ("ticker", "sentiment_rank", "news_count", "message_density") if c in metrics.columns]
        if len(cols) > 1:
            side = metrics[cols].copy()
            side["ticker"] = side["ticker"].astype(str).str.upper()
            out = out.merge(side, on="ticker", how="left")
    return out


def filter_table(df: pd.DataFrame, sector: str, min_news: int) -> pd.DataFrame:
    out = df.copy()
    if sector != "All" and "sector" in out.columns:
        out = out[out["sector"].fillna("").astype(str) == sector]
    if min_news > 0 and "news_count" in out.columns:
        out = out[out["news_count"].fillna(0) >= min_news]
    return out


def _finviz_auth_help(exc: Exception) -> str | None:
    text = str(exc)
    if "401" in text or "Unauthorized" in text:
        return (
            "**Finviz API token rejected (401).** Regenerate it: log in at "
            "[elite.finviz.com](https://elite.finviz.com) → **Settings → API** → copy token → "
            "update `FINVIZ_API_TOKEN` in `.env` → restart Streamlit."
        )
    return None


def _safe_error_text(exc: Exception) -> str:
    """Hide API tokens in URLs before displaying exceptions in Streamlit."""
    return re.sub(r"auth=[^&\\s]+", "auth=REDACTED", str(exc))


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
                "Try a wider range or turn off **Enable K-line rolling window**."
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
        cap = f"Live Finviz Elite `quote_export` · **{len(chart_bars)}** bars"
        if apply_chart_window:
            cap += f" in **{chart_window_label}** (UTC)"
        else:
            cap += " (full series)"
        cap += f" · [Open in Finviz]({stock_url})"
        st.caption(cap)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load live chart for {chart_ticker}: {_safe_error_text(exc)}")
        auth_help = _finviz_auth_help(exc)
        if auth_help:
            st.info(auth_help)

    ticker_news = live_news[live_news["ticker"].astype(str).str.upper() == chart_ticker.upper()]
    if ticker_news.empty:
        st.markdown(f":red[**{chart_ticker}** — no Finviz news (news-free)]")
    else:
        for _, item in ticker_news.head(10).iterrows():
            title = item.get("title", "")
            url = item.get("url", "")
            published = item.get("published", "")
            if url:
                st.markdown(f"- {published} · [{title}]({url})")
            else:
                st.markdown(f"- {published} · {title}")


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
        "**message_density**: Sparse (0–1), Moderate (2–3), Dense (4+)."
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
                help="Sparse: 0-1 articles · Moderate: 2-3 · Dense: 4+ (same date range as news_count)"
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


def render_social_tab(
    tickers: list[str],
    *,
    fetch_enabled: bool,
    window_start,
    window_end,
    window_label: str,
) -> None:
    """Self-contained social panel — separate from Finviz tabs and metrics."""
    st.caption(
        "Social sourcing via **Reddit** · **not connected to Finviz** news, K-line, or ranked table. "
        "Enable fetch in the sidebar; requests are rate-limited and cached for 15 minutes."
    )

    if not fetch_enabled:
        st.info(
            "Social fetch is **off** (default). Check **Enable social fetch** in the sidebar "
            "Social section, then click **Refresh social** if needed."
        )
        return

    social_messages, social_errs = load_live_social(tuple(tickers))
    social_metrics, social_filtered = build_social_metrics(
        social_messages,
        tickers,
        window_start=window_start,
        window_end=window_end,
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
            "Showing **sample** social posts (live Reddit access blocked, empty, or rate-limited). "
            "Integration demo only — Finviz tabs are unaffected."
        )

    total = int(social_metrics["social_count"].fillna(0).sum()) if not social_metrics.empty else 0
    st.metric(f"Social posts ({window_label})", total)

    if not social_metrics.empty:
        st.subheader("Per-ticker counts")
        show_cols = [c for c in ("ticker", "social_count", "social_density") if c in social_metrics.columns]
        view = social_metrics[show_cols].copy()
        if "social_density" in view.columns:
            view["social_density"] = view["social_density"].map(_format_density_label)
        st.dataframe(view, width="stretch", hide_index=True)

    st.subheader("Messages")
    if social_filtered.empty:
        st.info("No social posts in this date range.")
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
        f"IST 495 · **Live Finviz** · live scoring **{LIVE_SCORE_ENGINE.upper()}** · auto-refresh 60s"
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
        f"Finviz token from `.env`: `{token[:4]}…` "
        f"(compare with [Settings → API](https://elite.finviz.com/api_explanation))"
    )

    try:
        live_screener = load_live_screener(token)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Live Finviz screener unavailable: {_safe_error_text(exc)}")
        auth_help = _finviz_auth_help(exc)
        if auth_help:
            st.info(auth_help)
        return

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
        enable_chart_window = st.checkbox(
            "Enable K-line rolling window",
            value=False,
            help="Off by default — full Finviz history. Turn on to show date-range controls and zoom the chart.",
        )
        chart_window_start = None
        chart_window_end = None
        chart_window_label = "all bars"
        if enable_chart_window:
            st.caption("K-line rolling window (UTC calendar dates)")
            chart_range_preset = st.radio(
                "Chart quick range",
                ["Last 7 days", "Last 30 days", "Last 6 months", "All on page", "Custom"],
                index=0,
                key="chart_range_preset",
            )
            chart_default_start = today - timedelta(days=6)
            if chart_range_preset == "Custom":
                chart_custom_start = st.date_input(
                    "Chart from",
                    value=chart_default_start,
                    max_value=today,
                    key="chart_from",
                )
                chart_custom_end = st.date_input(
                    "Chart to",
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
                st.caption(f"Chart window: **{chart_window_label}**")

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
        st.caption("Optional Reddit social posts · separate from Finviz above.")
        fetch_social = st.checkbox(
            "Enable social fetch",
            value=False,
            help="Off by default — avoids extra social source calls while using Finviz tabs.",
        )
        social_range_preset = st.radio(
            "Social date range",
            ["Last 7 days", "Last 30 days", "Last 6 months", "All on page", "Custom"],
            index=0,
            key="social_range_preset",
        )
        social_default_start = today - timedelta(days=6)
        if social_range_preset == "Custom":
            social_custom_start = st.date_input(
                "Social from",
                value=social_default_start,
                max_value=today,
                key="social_from",
            )
            social_custom_end = st.date_input("Social to", value=today, max_value=today, key="social_to")
        else:
            social_custom_start = social_default_start
            social_custom_end = today
        social_window_start, social_window_end, social_window_label = resolve_news_window_preset(
            social_range_preset,
            custom_start=social_custom_start,
            custom_end=social_custom_end,
        )
        if st.button("Refresh social"):
            load_live_social.clear()
            st.rerun()

    sma_tuple = tuple(selected_smas) if selected_smas else default_sma_periods(period_label)

    screener = load_live_screener(token)
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
        st.caption(f"**Live Finviz fetch:** {fetched_at} · **{total_news}** articles in range ({window_label})")

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

        tab_chart, tab_table, tab_news, tab_social = st.tabs(
            ["Live Finviz chart", "Ranked tickers", "News viewer", "Social"]
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
        with tab_social:
            render_social_tab(
                tlist,
                fetch_enabled=fetch_social,
                window_start=social_window_start,
                window_end=social_window_end,
                window_label=social_window_label,
            )

    if auto_refresh:
        @st.fragment(run_every=60)
        def live_dashboard() -> None:
            _render_finviz_dashboard(load_live_screener(token))

        live_dashboard()
    else:
        _render_finviz_dashboard(screener)

    st.caption(f"Loaded {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")


if __name__ == "__main__":
    main()
