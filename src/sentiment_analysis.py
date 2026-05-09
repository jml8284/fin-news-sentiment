"""
Baseline sentiment using VADER -> data/processed/sentiment_results.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEAN_DEFAULT = PROJECT_ROOT / "data" / "processed" / "cleaned_news_data.csv"
SENT_OUT = PROJECT_ROOT / "data" / "processed" / "sentiment_results.csv"

_analyzer: SentimentIntensityAnalyzer | None = None


def get_analyzer() -> SentimentIntensityAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


def score_text(text: str) -> dict[str, float]:
    scores = get_analyzer().polarity_scores(text or "")
    return {
        "neg": scores["neg"],
        "neu": scores["neu"],
        "pos": scores["pos"],
        "compound": scores["compound"],
    }


def label_from_compound(compound: float) -> str:
    if compound >= 0.05:
        return "positive"
    if compound <= -0.05:
        return "negative"
    return "neutral"


def analyze_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    text = (df.get("title", "").fillna("") + ". " + df.get("summary", "").fillna("")).str.strip()
    scored = text.apply(lambda t: score_text(t))
    df["sentiment_neg"] = scored.apply(lambda x: x["neg"])
    df["sentiment_neu"] = scored.apply(lambda x: x["neu"])
    df["sentiment_pos"] = scored.apply(lambda x: x["pos"])
    df["sentiment_compound"] = scored.apply(lambda x: x["compound"])
    df["sentiment_label"] = df["sentiment_compound"].map(label_from_compound)
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", dest="in_path", type=Path, default=CLEAN_DEFAULT)
    parser.add_argument("--out", dest="out_path", type=Path, default=SENT_OUT)
    args = parser.parse_args()

    if not args.in_path.exists():
        raise FileNotFoundError(f"Missing {args.in_path}. Run clean_data.py first.")

    df = pd.read_csv(args.in_path)
    out_df = analyze_dataframe(df)
    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.out_path, index=False)
    print(f"Wrote {len(out_df)} rows to {args.out_path}")


if __name__ == "__main__":
    main()
