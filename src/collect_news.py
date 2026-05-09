"""
Collect financial news from a local demo CSV and/or RSS feeds.
Writes unified rows to data/raw/raw_news_data.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUT = RAW_DIR / "raw_news_data.csv"
DEMO_CSV = RAW_DIR / "demo_mock_news.csv"


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["ticker", "title", "summary", "published", "source", "url"]
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols]


def load_demo_to_dataframe() -> pd.DataFrame:
    if not DEMO_CSV.exists():
        raise FileNotFoundError(f"Missing demo file: {DEMO_CSV}")
    df = pd.read_csv(DEMO_CSV)
    return _ensure_columns(df)


def fetch_rss_entries(feed_url: str, max_items: int = 25) -> pd.DataFrame:
    """Parse an RSS/Atom feed into the project's column schema (ticker left blank)."""
    parsed = feedparser.parse(feed_url)
    rows: list[dict[str, str]] = []
    host = urlparse(feed_url).netloc or "rss"

    for entry in getattr(parsed, "entries", [])[:max_items]:
        title = getattr(entry, "title", "") or ""
        summary = ""
        if hasattr(entry, "summary"):
            summary = entry.summary or ""
        elif hasattr(entry, "description"):
            summary = entry.description or ""

        published = ""
        if hasattr(entry, "published"):
            published = entry.published or ""
        elif hasattr(entry, "updated"):
            published = entry.updated or ""

        link = ""
        if hasattr(entry, "link"):
            link = entry.link or ""

        rows.append(
            {
                "ticker": "",
                "title": title.strip(),
                "summary": summary.strip(),
                "published": published.strip(),
                "source": host,
                "url": link.strip(),
            }
        )

    return pd.DataFrame(rows)


def save_raw(df: pd.DataFrame, out_path: Path = DEFAULT_OUT) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_columns(df).to_csv(out_path, index=False)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect financial news (demo CSV and/or RSS).")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Load rows from data/raw/demo_mock_news.csv",
    )
    parser.add_argument(
        "--rss",
        action="append",
        default=[],
        metavar="URL",
        help="RSS feed URL (can be passed multiple times)",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=25,
        help="Max items per RSS feed",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output CSV path",
    )
    args = parser.parse_args()

    frames: list[pd.DataFrame] = []
    if args.demo:
        frames.append(load_demo_to_dataframe())
    for url in args.rss:
        frames.append(fetch_rss_entries(url, max_items=args.max_items))

    if not frames:
        parser.error("Provide --demo and/or one or more --rss URL")

    merged = pd.concat(frames, ignore_index=True)
    out = save_raw(merged, args.out)
    print(f"Wrote {len(merged)} rows to {out}")


if __name__ == "__main__":
    main()
