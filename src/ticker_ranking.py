"""
Aggregate sentiment and news counts by ticker -> data/processed/ticker_ranking.csv

news_count follows Finviz Elite quote-page news (professor ground truth).
Supplemental Google/Yahoo/SEC items are tracked separately and do not inflate counts.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.news_filters import (
    DEFAULT_ROLLING_WINDOW_DAYS,
    default_window_end,
    default_window_start,
    in_date_range,
    is_finviz_source,
    is_quality_supplemental,
    is_recent,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SENT_DEFAULT = PROJECT_ROOT / "data" / "processed" / "sentiment_results.csv"
RANK_OUT = PROJECT_ROOT / "data" / "processed" / "ticker_ranking.csv"


def density_bucket(count: int) -> str:
    if count >= 4:
        return "high"
    if count >= 2:
        return "medium"
    return "low"


def rank_tickers(
    df: pd.DataFrame,
    *,
    company_by_ticker: dict[str, str] | None = None,
    max_age_days: int = 7,
    rolling_window_days: int | None = DEFAULT_ROLLING_WINDOW_DAYS,
    window_start: date | None = None,
    window_end: date | None = None,
) -> pd.DataFrame:
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
                "supplemental_news_count",
                "positive_ratio",
                "negative_ratio",
                "message_density",
                "rolling_news_count",
            ]
        )

    companies = company_by_ticker or {}
    if window_start is None and window_end is None and rolling_window_days is not None and rolling_window_days > 0:
        window_end = default_window_end()
        window_start = default_window_start(days=rolling_window_days)
    elif window_start is not None and window_end is None:
        window_end = default_window_end()
    elif window_end is not None and window_start is None:
        window_start = window_end - timedelta(days=DEFAULT_ROLLING_WINDOW_DAYS - 1)

    use_date_window = window_start is not None and window_end is not None

    records: list[dict[str, object]] = []
    for ticker, sub in work.groupby("ticker"):
        finviz_rows = sub[sub["source"].map(is_finviz_source)]
        company = companies.get(ticker, "")
        supplemental_rows = sub[
            ~sub["source"].map(is_finviz_source)
            & sub.apply(
                lambda row: is_quality_supplemental(
                    str(row.get("title", "")),
                    str(row.get("summary", "")),
                    ticker,
                    company=company,
                    published=row.get("published", ""),
                    max_age_days=max_age_days,
                ),
                axis=1,
            )
        ]

        # Total Finviz quote-page count (professor ground truth).
        finviz_count = int(len(finviz_rows))
        supplemental_count = int(len(supplemental_rows))

        # Rolling window: sentiment + message density use Finviz news in date range.
        if use_date_window and "published" in finviz_rows.columns:
            in_window = finviz_rows[
                finviz_rows["published"].map(
                    lambda p: in_date_range(p, start=window_start, end=window_end)  # type: ignore[arg-type]
                )
            ]
        elif rolling_window_days is not None and rolling_window_days > 0 and "published" in finviz_rows.columns:
            in_window = finviz_rows[
                finviz_rows["published"].map(
                    lambda p: is_recent(p, max_age_days=rolling_window_days)
                )
            ]
        else:
            in_window = finviz_rows

        rolling_count = int(len(in_window))
        labels = in_window["sentiment_label"] if not in_window.empty else pd.Series(dtype=str)

        records.append(
            {
                "ticker": ticker,
                "avg_sentiment": float(in_window["sentiment_compound"].mean())
                if not in_window.empty
                else float("nan"),
                "news_count": finviz_count,
                "supplemental_news_count": supplemental_count,
                "positive_ratio": float((labels == "positive").mean()) if not labels.empty else float("nan"),
                "negative_ratio": float((labels == "negative").mean()) if not labels.empty else float("nan"),
                "rolling_news_count": rolling_count,
            }
        )

    agg = pd.DataFrame.from_records(records)
    agg["message_density"] = agg["rolling_news_count"].map(density_bucket)
    agg = agg.sort_values(["avg_sentiment", "news_count"], ascending=[False, False]).reset_index(
        drop=True
    )
    agg.insert(0, "rank", range(1, len(agg) + 1))
    return agg


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", dest="in_path", type=Path, default=SENT_DEFAULT)
    parser.add_argument("--out", dest="out_path", type=Path, default=RANK_OUT)
    parser.add_argument(
        "--window-days",
        type=int,
        default=DEFAULT_ROLLING_WINDOW_DAYS,
        help="Default rolling window ending today (days) for avg_sentiment and message_density",
    )
    parser.add_argument(
        "--window-start",
        type=str,
        default="",
        help="Optional YYYY-MM-DD start date (overrides --window-days when paired with --window-end)",
    )
    parser.add_argument(
        "--window-end",
        type=str,
        default="",
        help="Optional YYYY-MM-DD end date (inclusive)",
    )
    args = parser.parse_args()

    window_start: date | None = None
    window_end: date | None = None
    if args.window_start.strip():
        window_start = date.fromisoformat(args.window_start.strip())
    if args.window_end.strip():
        window_end = date.fromisoformat(args.window_end.strip())

    rolling_days: int | None = args.window_days
    if window_start is not None or window_end is not None:
        rolling_days = None

    if not args.in_path.exists():
        raise FileNotFoundError(f"Missing {args.in_path}. Run sentiment_analysis.py first.")

    df = pd.read_csv(args.in_path)
    companies: dict[str, str] = {}
    stocks_path = PROJECT_ROOT / "data" / "raw" / "raw_stock_data.csv"
    if stocks_path.exists():
        stocks = pd.read_csv(stocks_path)
        if "ticker" in stocks.columns and "company" in stocks.columns:
            for _, row in stocks.iterrows():
                ticker = str(row["ticker"]).upper().strip()
                if ticker:
                    companies[ticker] = str(row.get("company", "") or "")
    ranked = rank_tickers(
        df,
        company_by_ticker=companies,
        rolling_window_days=rolling_days,
        window_start=window_start,
        window_end=window_end,
    )
    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    ranked.to_csv(args.out_path, index=False)
    print(f"Wrote {len(ranked)} tickers to {args.out_path}")


if __name__ == "__main__":
    main()
