"""
Merge stock screener data with ticker-level sentiment rankings.

Input:
  data/raw/raw_stock_data.csv
  data/processed/ticker_ranking.csv

Output:
  data/processed/final_dataset.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STOCKS_DEFAULT = PROJECT_ROOT / "data" / "raw" / "raw_stock_data.csv"
RANK_DEFAULT = PROJECT_ROOT / "data" / "processed" / "ticker_ranking.csv"
FINAL_OUT = PROJECT_ROOT / "data" / "processed" / "final_dataset.csv"

FINAL_COLUMNS = [
    "rank",
    "ticker",
    "company",
    "sector",
    "price",
    "change_pct",
    "volume",
    "market_cap",
    "pe",
    "avg_sentiment",
    "news_count",
    "positive_ratio",
    "negative_ratio",
    "message_density",
]


def _normalize_ticker(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.upper().str.strip()


def merge_stock_and_sentiment(
    stocks: pd.DataFrame,
    ranking: pd.DataFrame,
) -> pd.DataFrame:
    stocks = stocks.copy()
    ranking = ranking.copy()

    stocks["ticker"] = _normalize_ticker(stocks["ticker"])
    ranking["ticker"] = _normalize_ticker(ranking["ticker"])

    merged = stocks.merge(ranking, on="ticker", how="left", suffixes=("", "_rank"))

    if "rank_rank" in merged.columns:
        merged["rank"] = merged["rank_rank"].fillna(merged.get("rank"))
        merged = merged.drop(columns=["rank_rank"], errors="ignore")

    # Tickers with news but no stock row (edge case).
    missing = ranking[~ranking["ticker"].isin(stocks["ticker"])]
    if not missing.empty:
        extra = missing.copy()
        for col in ("company", "sector", "price", "change_pct", "volume", "market_cap", "pe"):
            if col not in extra.columns:
                extra[col] = ""
        merged = pd.concat([merged, extra], ignore_index=True)

    for col in FINAL_COLUMNS:
        if col not in merged.columns:
            merged[col] = pd.NA

    merged = merged[FINAL_COLUMNS]
    merged = merged.sort_values(
        ["rank", "avg_sentiment", "news_count"],
        ascending=[True, False, False],
        na_position="last",
    ).reset_index(drop=True)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge stock data with sentiment rankings.")
    parser.add_argument("--stocks", type=Path, default=STOCKS_DEFAULT)
    parser.add_argument("--ranking", type=Path, default=RANK_DEFAULT)
    parser.add_argument("--out", type=Path, default=FINAL_OUT)
    args = parser.parse_args()

    if not args.stocks.exists():
        raise FileNotFoundError(f"Missing {args.stocks}. Run collect_stocks first.")
    if not args.ranking.exists():
        raise FileNotFoundError(f"Missing {args.ranking}. Run ticker_ranking first.")

    stocks = pd.read_csv(args.stocks)
    ranking = pd.read_csv(args.ranking)
    final = merge_stock_and_sentiment(stocks, ranking)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(args.out, index=False)
    with_news = final["news_count"].notna().sum() if "news_count" in final.columns else 0
    print(f"Wrote {len(final)} rows to {args.out} ({with_news} with sentiment)")


if __name__ == "__main__":
    main()
