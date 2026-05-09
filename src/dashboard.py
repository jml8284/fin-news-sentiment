"""
Streamlit dashboard: ranked tickers + recent headlines (demo pipeline).
Run from repo root: streamlit run src/dashboard.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RANK_PATH = PROJECT_ROOT / "data" / "processed" / "ticker_ranking.csv"
SENT_PATH = PROJECT_ROOT / "data" / "processed" / "sentiment_results.csv"


@st.cache_data
def load_ranking() -> pd.DataFrame:
    if not RANK_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(RANK_PATH)


@st.cache_data
def load_sentiment() -> pd.DataFrame:
    if not SENT_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(SENT_PATH)


def main() -> None:
    st.set_page_config(page_title="Fin News Sentiment", layout="wide")
    st.title("Financial News Sentiment — Dashboard (prototype)")
    st.caption("IST 495 · Load processed CSVs from data/processed/ after running the pipeline.")

    ranked = load_ranking()
    sentiment = load_sentiment()

    if ranked.empty:
        st.warning(
            "No ticker ranking found. From the repo root run:\n"
            "`python -m src.collect_news --demo` → `python -m src.clean_data` → "
            "`python -m src.sentiment_analysis` → `python -m src.ticker_ranking`"
        )
        return

    st.subheader("Ranked tickers")
    st.dataframe(ranked, use_container_width=True, hide_index=True)

    if not sentiment.empty:
        st.subheader("Recent news (with sentiment)")
        cols = [c for c in ("ticker", "title", "sentiment_label", "sentiment_compound", "source", "published", "url") if c in sentiment.columns]
        st.dataframe(sentiment[cols].head(50), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
