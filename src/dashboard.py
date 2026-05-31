"""
Streamlit dashboard: stock metrics + sentiment rankings + news viewer.

Run from repo root:
  streamlit run src/dashboard.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FINAL_PATH = PROJECT_ROOT / "data" / "processed" / "final_dataset.csv"
RANK_PATH = PROJECT_ROOT / "data" / "processed" / "ticker_ranking.csv"
STOCKS_PATH = PROJECT_ROOT / "data" / "raw" / "raw_stock_data.csv"
SENT_PATH = PROJECT_ROOT / "data" / "processed" / "sentiment_results.csv"


@st.cache_data
def load_final_dataset() -> pd.DataFrame:
    if FINAL_PATH.exists():
        return pd.read_csv(FINAL_PATH)
    return pd.DataFrame()


@st.cache_data
def load_ranking() -> pd.DataFrame:
    if RANK_PATH.exists():
        return pd.read_csv(RANK_PATH)
    return pd.DataFrame()


@st.cache_data
def load_stocks() -> pd.DataFrame:
    if STOCKS_PATH.exists():
        return pd.read_csv(STOCKS_PATH)
    return pd.DataFrame()


@st.cache_data
def load_sentiment() -> pd.DataFrame:
    if SENT_PATH.exists():
        return pd.read_csv(SENT_PATH)
    return pd.DataFrame()


def build_summary_table() -> pd.DataFrame:
    final = load_final_dataset()
    if not final.empty:
        return final

    stocks = load_stocks()
    ranking = load_ranking()
    if stocks.empty and ranking.empty:
        return pd.DataFrame()

    if not stocks.empty and not ranking.empty:
        stocks = stocks.copy()
        ranking = ranking.copy()
        stocks["ticker"] = stocks["ticker"].astype(str).str.upper()
        ranking["ticker"] = ranking["ticker"].astype(str).str.upper()
        return stocks.merge(ranking, on="ticker", how="outer")

    return stocks if not stocks.empty else ranking


def filter_table(df: pd.DataFrame, sector: str, min_news: int) -> pd.DataFrame:
    out = df.copy()
    if sector != "All" and "sector" in out.columns:
        out = out[out["sector"].fillna("").astype(str) == sector]
    if min_news > 0 and "news_count" in out.columns:
        out = out[out["news_count"].fillna(0) >= min_news]
    return out


def main() -> None:
    st.set_page_config(page_title="Fin News Sentiment", layout="wide")
    st.title("Financial News Sentiment Dashboard")
    st.caption("IST 495 · Stocks from Finviz + VADER sentiment + ranked tickers")

    summary = build_summary_table()
    sentiment = load_sentiment()

    if summary.empty:
        st.warning(
            "No processed data found. Run the pipeline first:\n\n"
            "`python -m src.run_pipeline --demo`\n\n"
            "Or step by step: collect_stocks → collect_news → clean_data → "
            "sentiment_analysis → ticker_ranking → merge_data"
        )
        return

    sectors = ["All"]
    if "sector" in summary.columns:
        sectors += sorted(s for s in summary["sector"].dropna().unique() if str(s).strip())

    with st.sidebar:
        st.header("Filters")
        sector_filter = st.selectbox("Sector", sectors)
        min_news = st.slider("Minimum news count", 0, 10, 0)
        sort_by = st.selectbox(
            "Sort by",
            [c for c in ("avg_sentiment", "change_pct", "volume", "news_count", "rank") if c in summary.columns],
        )
        sort_asc = st.checkbox("Ascending", value=False)

    filtered = filter_table(summary, sector_filter, min_news)
    if sort_by in filtered.columns:
        filtered = filtered.sort_values(sort_by, ascending=sort_asc, na_position="last")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tickers", len(filtered))
    if "avg_sentiment" in filtered.columns:
        c2.metric("Avg sentiment", f"{filtered['avg_sentiment'].mean():.3f}")
    if "news_count" in filtered.columns:
        c3.metric("Total news", int(filtered["news_count"].fillna(0).sum()))
    if "change_pct" in filtered.columns:
        c4.metric("Avg change %", f"{filtered['change_pct'].mean():.2f}%")

    st.subheader("Ranked tickers (stock + sentiment)")
    display_cols = [
        c
        for c in (
            "rank",
            "ticker",
            "company",
            "sector",
            "price",
            "change_pct",
            "volume",
            "avg_sentiment",
            "news_count",
            "message_density",
            "positive_ratio",
            "negative_ratio",
        )
        if c in filtered.columns
    ]
    st.dataframe(
        filtered[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "price": st.column_config.NumberColumn(format="%.2f"),
            "change_pct": st.column_config.NumberColumn(format="%.2f"),
            "volume": st.column_config.NumberColumn(format="%d"),
            "avg_sentiment": st.column_config.NumberColumn(format="%.3f"),
            "positive_ratio": st.column_config.NumberColumn(format="%.0%"),
            "negative_ratio": st.column_config.NumberColumn(format="%.0%"),
        },
    )

    if "avg_sentiment" in filtered.columns and "ticker" in filtered.columns:
        chart_df = filtered.dropna(subset=["avg_sentiment", "ticker"])
        if not chart_df.empty:
            st.subheader("Sentiment by ticker")
            fig = px.bar(
                chart_df,
                x="ticker",
                y="avg_sentiment",
                color="avg_sentiment",
                color_continuous_scale="RdYlGn",
                title="Average sentiment score",
            )
            fig.update_layout(showlegend=False, height=400)
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("News viewer")
    if sentiment.empty:
        st.info("No sentiment_results.csv found.")
        return

    tickers_with_news = sorted(
        t for t in sentiment["ticker"].fillna("").astype(str).str.upper().unique() if t
    )
    if not tickers_with_news:
        st.info("No ticker-tagged news in sentiment results.")
        return

    selected = st.selectbox("Select ticker", tickers_with_news)
    news_cols = [
        c
        for c in (
            "title",
            "sentiment_label",
            "sentiment_compound",
            "source",
            "published",
            "summary",
            "url",
        )
        if c in sentiment.columns
    ]
    ticker_news = sentiment[
        sentiment["ticker"].fillna("").astype(str).str.upper() == selected
    ][news_cols]

    st.write(f"**{len(ticker_news)}** articles for **{selected}**")
    st.dataframe(ticker_news, use_container_width=True, hide_index=True)

    for _, row in ticker_news.head(10).iterrows():
        title = row.get("title", "")
        url = row.get("url", "")
        label = row.get("sentiment_label", "")
        compound = row.get("sentiment_compound", "")
        if url:
            st.markdown(f"- [{title}]({url}) · **{label}** ({compound})")
        else:
            st.markdown(f"- {title} · **{label}** ({compound})")


if __name__ == "__main__":
    main()
