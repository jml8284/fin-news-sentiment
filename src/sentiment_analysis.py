"""
Sentiment scoring for cleaned news -> data/processed/sentiment_results.csv

Default engine: VADER. Use --engine finbert for finance-tuned transformer scores.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.sentiment_engines import (
    SUPPORTED_ENGINES,
    analyze_dataframe,
    label_from_compound,
    score_text,
    write_engine_metadata,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEAN_DEFAULT = PROJECT_ROOT / "data" / "processed" / "cleaned_news_data.csv"
SENT_OUT = PROJECT_ROOT / "data" / "processed" / "sentiment_results.csv"
ENGINE_META = PROJECT_ROOT / "data" / "processed" / "sentiment_engine.txt"

__all__ = ["analyze_dataframe", "label_from_compound", "score_text"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", dest="in_path", type=Path, default=CLEAN_DEFAULT)
    parser.add_argument("--out", dest="out_path", type=Path, default=SENT_OUT)
    parser.add_argument(
        "--engine",
        choices=SUPPORTED_ENGINES,
        default="vader",
        help="Sentiment model (finbert needs transformers + torch)",
    )
    args = parser.parse_args()

    if not args.in_path.exists():
        raise FileNotFoundError(f"Missing {args.in_path}. Run clean_data.py first.")

    df = pd.read_csv(args.in_path)
    out_df = analyze_dataframe(df, engine=args.engine)
    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.out_path, index=False)
    write_engine_metadata(args.engine, ENGINE_META)
    print(f"Wrote {len(out_df)} rows to {args.out_path} ({args.engine})")


if __name__ == "__main__":
    main()
