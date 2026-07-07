"""
Store processed pipeline outputs in MongoDB.

Requires MongoDB running locally or a Atlas URI in .env:
  MONGODB_URI=mongodb://localhost:27017
  MONGODB_DB=fin_news_sentiment

Example:
  python -m src.store_mongo
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

FINAL_PATH = PROJECT_ROOT / "data" / "processed" / "final_dataset.csv"
SENT_PATH = PROJECT_ROOT / "data" / "processed" / "sentiment_results.csv"
STOCKS_PATH = PROJECT_ROOT / "data" / "raw" / "raw_stock_data.csv"


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    return df.where(pd.notna(df), None).to_dict(orient="records")


def store_pipeline_run(
    *,
    uri: str,
    db_name: str,
    final_path: Path = FINAL_PATH,
    sent_path: Path = SENT_PATH,
    stocks_path: Path = STOCKS_PATH,
) -> None:
    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise RuntimeError("Install pymongo: pip install pymongo") from exc

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[db_name]

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    meta = {
        "run_id": run_id,
        "stored_at": datetime.now(timezone.utc).isoformat(),
        "source": "fin-news-sentiment pipeline",
    }
    db["pipeline_runs"].insert_one(meta)

    if final_path.exists():
        df = pd.read_csv(final_path)
        if not df.empty:
            db["final_dataset"].delete_many({})
            db["final_dataset"].insert_many(_df_to_records(df))

    if sent_path.exists():
        df = pd.read_csv(sent_path)
        if not df.empty:
            db["sentiment_results"].delete_many({})
            db["sentiment_results"].insert_many(_df_to_records(df))

    if stocks_path.exists():
        df = pd.read_csv(stocks_path)
        if not df.empty:
            db["raw_stocks"].delete_many({})
            db["raw_stocks"].insert_many(_df_to_records(df))

    print(f"Stored pipeline run {run_id} to MongoDB database '{db_name}'")


def main() -> None:
    parser = argparse.ArgumentParser(description="Store processed CSVs in MongoDB.")
    parser.add_argument(
        "--uri",
        default=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        help="MongoDB connection URI",
    )
    parser.add_argument(
        "--db",
        default=os.getenv("MONGODB_DB", "fin_news_sentiment"),
        help="Database name",
    )
    args = parser.parse_args()
    store_pipeline_run(uri=args.uri, db_name=args.db)


if __name__ == "__main__":
    main()
