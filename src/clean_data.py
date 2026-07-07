"""
Normalize and lightly clean raw news CSV -> data/processed/cleaned_news_data.csv
"""
from __future__ import annotations

import argparse
import re
from html import unescape
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DEFAULT = PROJECT_ROOT / "data" / "raw" / "raw_news_data.csv"
PROC_DIR = PROJECT_ROOT / "data" / "processed"
CLEAN_OUT = PROC_DIR / "cleaned_news_data.csv"


_WS = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]+>")


def clean_text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = unescape(_TAG.sub(" ", str(value))).strip()
    s = _WS.sub(" ", s)
    return s


def clean_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ("title", "summary", "source", "url", "ticker", "published", "collected_at"):
        if col in df.columns:
            df[col] = df[col].map(clean_text)
    df = df.drop_duplicates(subset=["url", "title"], keep="first")
    df = df[df["title"].str.len() > 0]
    return df.reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", dest="in_path", type=Path, default=RAW_DEFAULT)
    parser.add_argument("--out", dest="out_path", type=Path, default=CLEAN_OUT)
    args = parser.parse_args()

    if not args.in_path.exists():
        raise FileNotFoundError(
            f"Input not found: {args.in_path}. Run: python -m src.collect_news --demo"
        )

    df = pd.read_csv(args.in_path)
    cleaned = clean_frame(df)
    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(args.out_path, index=False)
    print(f"Wrote {len(cleaned)} rows to {args.out_path}")


if __name__ == "__main__":
    main()
