"""
Run the full fin-news-sentiment production pipeline.

Default (no flags): Finviz Elite 20-stock screener + per-ticker news + sentiment + dashboard data.

Setup:
  cp .env.example .env   # add FINVIZ_API_TOKEN

Run:
  python -m src.run_pipeline
  streamlit run src/dashboard.py

Offline only:
  python -m src.run_pipeline --demo
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from src.finviz_config import get_api_token

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_step(cmd: list[str]) -> None:
    print(f"\n>>> {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the production pipeline (Finviz Elite screener + news + sentiment)."
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Offline demo CSVs only (not for production)",
    )
    parser.add_argument(
        "--free-scrape",
        action="store_true",
        help="Use free Finviz HTML scrape instead of Elite export (no API token)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Number of tickers from screener (default: 20)",
    )
    parser.add_argument(
        "--tickers",
        default="",
        help="Optional comma-separated tickers for news (defaults to all from stock CSV)",
    )
    parser.add_argument(
        "--sources",
        default="finviz,google,yahoo,sec",
        help="News sources for per-ticker collection",
    )
    parser.add_argument(
        "--max-items-per-source",
        type=int,
        default=8,
        help="Max Google/Yahoo/SEC items per ticker",
    )
    parser.add_argument(
        "--finviz-max-items",
        type=int,
        default=0,
        help="Max Finviz quote-page news rows per ticker (0 = no cap)",
    )
    parser.add_argument("--news-sleep", type=float, default=1.0, help="Seconds between ticker news requests")
    parser.add_argument("--signal", default="most_active", help="Free-scrape signal preset only")
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run sentiment benchmark evaluation after pipeline",
    )
    parser.add_argument(
        "--finbert",
        action="store_true",
        help="Use FinBERT instead of VADER for sentiment (requires transformers + torch)",
    )
    parser.add_argument(
        "--evaluate-models",
        default="",
        help="Models for --evaluate (vader, finbert, all). Default: vader, or all when --finbert",
    )
    parser.add_argument(
        "--mongo",
        action="store_true",
        help="Store results in MongoDB (requires running MongoDB + pymongo)",
    )
    args = parser.parse_args()

    py = sys.executable

    if args.demo:
        run_step([py, "-m", "src.collect_stocks", "--demo"])
        run_step([py, "-m", "src.collect_news", "--demo"])
    elif args.free_scrape:
        run_step(
            [
                py,
                "-m",
                "src.collect_stocks",
                "--free-scrape",
                "--signal",
                args.signal,
                "--top-n",
                str(args.top_n),
            ]
        )
        news_cmd = _news_command(py, args)
        run_step(news_cmd)
    else:
        # Production default: Finviz Elite technical screener
        get_api_token()
        print("Using Finviz Elite production screener (technical-gainers, top 20).")
        run_step(
            [
                py,
                "-m",
                "src.collect_stocks",
                "--elite",
                "--preset",
                "technical-gainers",
                "--top-n",
                str(args.top_n),
            ]
        )
        run_step(_news_command(py, args))

    run_step([py, "-m", "src.clean_data"])
    sentiment_cmd = [py, "-m", "src.sentiment_analysis"]
    if args.finbert:
        sentiment_cmd.extend(["--engine", "finbert"])
    run_step(sentiment_cmd)
    run_step([py, "-m", "src.ticker_ranking", "--window-days", "7"])
    run_step([py, "-m", "src.merge_data"])

    if args.evaluate:
        eval_models = args.evaluate_models.strip() or ("all" if args.finbert else "vader")
        run_step([py, "-m", "src.evaluate_sentiment", "--models", eval_models])

    if args.mongo:
        try:
            run_step([py, "-m", "src.store_mongo"])
        except subprocess.CalledProcessError:
            print("MongoDB store skipped (is MongoDB running? pip install pymongo?)")

    print("\nPipeline complete. Launch dashboard with: streamlit run src/dashboard.py")


def _news_command(py: str, args: argparse.Namespace) -> list[str]:
    cmd = [
        py,
        "-m",
        "src.collect_news",
        "--from-stocks",
        "--sources",
        args.sources,
        "--max-items-per-source",
        str(args.max_items_per_source),
        "--finviz-max-items",
        str(args.finviz_max_items),
        "--sleep",
        str(args.news_sleep),
        "--top-n",
        str(args.top_n),
    ]
    if args.tickers:
        cmd.extend(["--tickers", args.tickers])
    return cmd


if __name__ == "__main__":
    main()
