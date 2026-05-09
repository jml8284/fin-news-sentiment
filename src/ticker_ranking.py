"""
Aggregate sentiment and news counts by ticker -> data/processed/ticker_ranking.csv
Rows without a ticker are skipped for ranking (RSS-only rows).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SENT_DEFAULT = PROJECT_ROOT / "data" / "processed" / "sentiment_results.csv"
RANK_OUT = PROJECT_ROOT / "data" / "processed" / "ticker_ranking.csv"


def density_bucket(count: int) -> str:
    if count >= 4:
        return "high"
    if count >= 2:
        return "medium"
    return "low"


def rank_tickers(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["ticker"] = work["ticker"].fillna("").astype(str).str.upper().str.strip()
    work = work[work["ticker"].str.len() > 0]
    if work.empty:
        return pd.DataFrame(
            columns=[
                "rank",
                "ticker",
                "avg_sentiment",
                "news_count",
                "positive_ratio",
                "negative_ratio",
                "message_density",
            ]
        )

    records: list[dict[str, object]] = []
    for ticker, sub in work.groupby("ticker"):
        labels = sub["sentiment_label"]
        records.append(
            {
                "ticker": ticker,
                "avg_sentiment": float(sub["sentiment_compound"].mean()),
                "news_count": int(len(sub)),
                "positive_ratio": float((labels == "positive").mean()),
                "negative_ratio": float((labels == "negative").mean()),
            }
        )

    agg = pd.DataFrame.from_records(records)
    agg["message_density"] = agg["news_count"].map(density_bucket)
    agg = agg.sort_values(["avg_sentiment", "news_count"], ascending=[False, False]).reset_index(
        drop=True
    )
    agg.insert(0, "rank", range(1, len(agg) + 1))
    return agg


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", dest="in_path", type=Path, default=SENT_DEFAULT)
    parser.add_argument("--out", dest="out_path", type=Path, default=RANK_OUT)
    args = parser.parse_args()

    if not args.in_path.exists():
        raise FileNotFoundError(f"Missing {args.in_path}. Run sentiment_analysis.py first.")

    df = pd.read_csv(args.in_path)
    ranked = rank_tickers(df)
    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    ranked.to_csv(args.out_path, index=False)
    print(f"Wrote {len(ranked)} tickers to {args.out_path}")


if __name__ == "__main__":
    main()
