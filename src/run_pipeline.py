"""
Run the full fin-news-sentiment pipeline from the repository root.

Examples:
  python -m src.run_pipeline --demo
  python -m src.run_pipeline --elite
  python -m src.run_pipeline --top-n 10 --tickers NVDA,F,INTC
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_step(cmd: list[str]) -> None:
    print(f"\n>>> {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full data pipeline.")
    parser.add_argument("--demo", action="store_true", help="Use demo stock/news CSVs")
    parser.add_argument(
        "--elite",
        action="store_true",
        help="Use Finviz Elite export (20-stock technical screener + Elite stock pages)",
    )
    parser.add_argument("--top-n", type=int, default=20, help="Finviz / stock ticker limit")
    parser.add_argument(
        "--tickers",
        default="",
        help="Comma-separated tickers for news (optional)",
    )
    parser.add_argument(
        "--sources",
        default="",
        help="News sources (default: finviz,google,yahoo for --elite else google,yahoo,finviz)",
    )
    parser.add_argument("--max-items-per-source", type=int, default=5)
    parser.add_argument("--signal", default="most_active", help="Free Finviz signal preset")
    args = parser.parse_args()

    if not args.sources:
        args.sources = "finviz,google,yahoo" if args.elite else "google,yahoo,finviz"

    py = sys.executable

    if args.demo:
        run_step([py, "-m", "src.collect_stocks", "--demo"])
        run_step([py, "-m", "src.collect_news", "--demo"])
    elif args.elite:
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
        news_cmd = [
            py,
            "-m",
            "src.collect_news",
            "--from-stocks",
            "--sources",
            args.sources,
            "--max-items-per-source",
            str(args.max_items_per_source),
            "--top-n",
            str(args.top_n),
        ]
        if args.tickers:
            news_cmd.extend(["--tickers", args.tickers])
        run_step(news_cmd)
    else:
        run_step(
            [
                py,
                "-m",
                "src.collect_stocks",
                "--signal",
                args.signal,
                "--top-n",
                str(args.top_n),
            ]
        )
        news_cmd = [
            py,
            "-m",
            "src.collect_news",
            "--from-stocks",
            "--sources",
            args.sources,
            "--max-items-per-source",
            str(args.max_items_per_source),
        ]
        if args.tickers:
            news_cmd.extend(["--tickers", args.tickers])
        else:
            news_cmd.extend(["--top-n", str(args.top_n)])
        run_step(news_cmd)

    run_step([py, "-m", "src.clean_data"])
    run_step([py, "-m", "src.sentiment_analysis"])
    run_step([py, "-m", "src.ticker_ranking"])
    run_step([py, "-m", "src.merge_data"])
    print("\nPipeline complete. Launch dashboard with: streamlit run src/dashboard.py")


if __name__ == "__main__":
    main()
