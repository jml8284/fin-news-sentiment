"""
Collect financial news from demo CSV, RSS feeds, and per-ticker sources.

Writes unified rows to data/raw/raw_news_data.csv

Examples:
  python -m src.collect_news --demo
  python -m src.collect_news --from-stocks --top-n 5
  python -m src.collect_news --from-stocks --tickers NVDA,AAPL --sources google,yahoo
"""
from __future__ import annotations

import argparse
import logging
import re
import time
from html import unescape
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import feedparser
import pandas as pd
from bs4 import BeautifulSoup

from src.collect_stocks import fetch_html
from src.finviz_config import build_elite_stock_url, get_api_token

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUT = RAW_DIR / "raw_news_data.csv"
DEMO_CSV = RAW_DIR / "demo_mock_news.csv"
STOCKS_DEFAULT = RAW_DIR / "raw_stock_data.csv"

NEWS_COLUMNS = ["ticker", "title", "summary", "published", "source", "url"]
AVAILABLE_SOURCES = ("google", "yahoo", "finviz")
_TAG_RE = re.compile(r"<[^>]+>")

logger = logging.getLogger(__name__)


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in NEWS_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[NEWS_COLUMNS]


def _strip_html(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = unescape(_TAG_RE.sub(" ", str(value)))
    return re.sub(r"\s+", " ", text).strip()


def load_demo_to_dataframe() -> pd.DataFrame:
    if not DEMO_CSV.exists():
        raise FileNotFoundError(f"Missing demo file: {DEMO_CSV}")
    df = pd.read_csv(DEMO_CSV)
    return _ensure_columns(df)


def load_tickers_from_stocks(
    stocks_path: Path = STOCKS_DEFAULT,
    *,
    top_n: int | None = None,
    tickers: list[str] | None = None,
) -> list[str]:
    if not stocks_path.exists():
        raise FileNotFoundError(
            f"Stock file not found: {stocks_path}. Run: python -m src.collect_stocks --demo"
        )

    df = pd.read_csv(stocks_path)
    if "ticker" not in df.columns:
        raise KeyError(f"Expected a ticker column in {stocks_path}")

    if tickers:
        wanted = {t.strip().upper() for t in tickers if t.strip()}
        series = df["ticker"].astype(str).str.upper().str.strip()
        found = [t for t in series.tolist() if t in wanted]
        missing = sorted(wanted - set(found))
        for ticker in missing:
            logger.warning("Ticker %s not found in %s; skipping lookup row", ticker, stocks_path)
            found.append(ticker)
        result = found
    else:
        result = df["ticker"].astype(str).str.upper().str.strip().tolist()

    deduped: list[str] = []
    seen: set[str] = set()
    for ticker in result:
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        deduped.append(ticker)

    if top_n is not None:
        deduped = deduped[:top_n]
    return deduped


def fetch_rss_entries(
    feed_url: str,
    *,
    ticker: str = "",
    source_label: str | None = None,
    max_items: int = 25,
) -> pd.DataFrame:
    """Parse an RSS/Atom feed into the project's column schema."""
    parsed = feedparser.parse(feed_url)
    rows: list[dict[str, str]] = []
    host = source_label or urlparse(feed_url).netloc or "rss"

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
                "ticker": ticker,
                "title": _strip_html(title),
                "summary": _strip_html(summary),
                "published": published.strip(),
                "source": host,
                "url": link.strip(),
            }
        )

    return pd.DataFrame(rows)


def google_news_feed_url(ticker: str) -> str:
    query = quote_plus(f"{ticker} stock")
    return (
        "https://news.google.com/rss/search?"
        f"q={query}&hl=en-US&gl=US&ceid=US:en"
    )


def yahoo_finance_feed_url(ticker: str) -> str:
    return (
        "https://feeds.finance.yahoo.com/rss/2.0/headline"
        f"?s={quote_plus(ticker)}&region=US&lang=en-US"
    )


def fetch_google_news(ticker: str, *, max_items: int = 10) -> pd.DataFrame:
    url = google_news_feed_url(ticker)
    return fetch_rss_entries(
        url,
        ticker=ticker,
        source_label="Google News",
        max_items=max_items,
    )


def fetch_yahoo_news(ticker: str, *, max_items: int = 10) -> pd.DataFrame:
    url = yahoo_finance_feed_url(ticker)
    return fetch_rss_entries(
        url,
        ticker=ticker,
        source_label="Yahoo Finance",
        max_items=max_items,
    )


def fetch_finviz_news(
    ticker: str,
    *,
    max_items: int = 10,
    auth_token: str | None = None,
    use_elite: bool = True,
) -> pd.DataFrame:
    """
    Fetch news from Finviz quote/stock page.

    Uses Elite stock URL (stock?t=TICKER) when use_elite=True, which matches
    the professor's chart page link pattern instead of the free export URL.
    """
    if use_elite:
        token = auth_token
        if token is None:
            try:
                token = get_api_token(None)
            except RuntimeError:
                token = None
        url = build_elite_stock_url(ticker, token)
        source_label = "Finviz Elite"
    else:
        url = f"https://finviz.com/quote.ashx?t={quote_plus(ticker)}"
        source_label = "Finviz"

    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for table in soup.select("table.fullview-news-outer, table#news-table, table.news-table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 2:
                continue
            published = cells[0].get_text(strip=True)
            link = cells[1].find("a")
            if link is None:
                continue
            title = link.get_text(strip=True)
            href = link.get("href", "").strip()
            if not title:
                continue
            rows.append(
                {
                    "ticker": ticker,
                    "title": title,
                    "summary": "",
                    "published": published,
                    "source": source_label,
                    "url": href,
                }
            )
            if len(rows) >= max_items:
                break
        if rows:
            break

    return pd.DataFrame(rows)


def collect_news_for_ticker(
    ticker: str,
    *,
    sources: list[str],
    max_items_per_source: int = 10,
    finviz_elite: bool = True,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    auth_token = None
    if finviz_elite and "finviz" in sources:
        try:
            auth_token = get_api_token(None)
        except RuntimeError:
            auth_token = None

    def _finviz_fetch(t: str, max_items: int) -> pd.DataFrame:
        return fetch_finviz_news(
            t,
            max_items=max_items,
            auth_token=auth_token,
            use_elite=finviz_elite,
        )

    fetchers = {
        "google": fetch_google_news,
        "yahoo": fetch_yahoo_news,
        "finviz": _finviz_fetch,
    }

    for source in sources:
        fetcher = fetchers.get(source)
        if fetcher is None:
            continue
        try:
            df = fetcher(ticker, max_items=max_items_per_source)
            if not df.empty:
                frames.append(df)
        except Exception as exc:  # noqa: BLE001 - continue other sources/tickers
            logger.warning("Failed %s news for %s: %s", source, ticker, exc)

    if not frames:
        return pd.DataFrame(columns=NEWS_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def collect_news_for_tickers(
    tickers: list[str],
    *,
    sources: list[str],
    max_items_per_source: int = 10,
    sleep_seconds: float = 0.5,
    finviz_elite: bool = True,
) -> tuple[pd.DataFrame, list[str]]:
    frames: list[pd.DataFrame] = []
    missing: list[str] = []

    for ticker in tickers:
        df = collect_news_for_ticker(
            ticker,
            sources=sources,
            max_items_per_source=max_items_per_source,
            finviz_elite=finviz_elite,
        )
        if df.empty:
            missing.append(ticker)
            logger.info("No news found for %s", ticker)
        else:
            logger.info("Collected %s news rows for %s", len(df), ticker)
            frames.append(df)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    if not frames:
        return pd.DataFrame(columns=NEWS_COLUMNS), missing

    merged = pd.concat(frames, ignore_index=True)
    merged = merged.drop_duplicates(subset=["ticker", "url", "title"], keep="first")
    merged = merged[merged["title"].str.len() > 0].reset_index(drop=True)
    return _ensure_columns(merged), missing


def save_raw(df: pd.DataFrame, out_path: Path = DEFAULT_OUT) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_columns(df).to_csv(out_path, index=False)
    return out_path


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Collect financial news (demo CSV and/or RSS).")
    parser.add_argument("--demo", action="store_true", help="Load rows from demo_mock_news.csv")
    parser.add_argument(
        "--from-stocks",
        action="store_true",
        help="Collect news for tickers in raw_stock_data.csv",
    )
    parser.add_argument(
        "--stocks-path",
        type=Path,
        default=STOCKS_DEFAULT,
        help="Stock CSV used with --from-stocks",
    )
    parser.add_argument(
        "--tickers",
        default="",
        help="Comma-separated tickers (optional; defaults to all in stock CSV)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=None,
        help="Limit number of tickers from stock CSV",
    )
    parser.add_argument(
        "--sources",
        default="google,yahoo,finviz",
        help=f"Comma-separated sources: {','.join(AVAILABLE_SOURCES)}",
    )
    parser.add_argument(
        "--rss",
        action="append",
        default=[],
        metavar="URL",
        help="Additional RSS feed URL (can be passed multiple times)",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=25,
        help="Max items per generic RSS feed",
    )
    parser.add_argument(
        "--max-items-per-source",
        type=int,
        default=10,
        help="Max items per ticker/source when using --from-stocks",
    )
    parser.add_argument(
        "--finviz-free",
        action="store_true",
        help="Use free finviz.com quote pages instead of Elite stock?t= URLs",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Delay between ticker requests",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output CSV path")
    args = parser.parse_args()

    sources = [s.strip().lower() for s in args.sources.split(",") if s.strip()]
    unknown = sorted(set(sources) - set(AVAILABLE_SOURCES))
    if unknown:
        parser.error(f"Unknown sources: {', '.join(unknown)}")

    frames: list[pd.DataFrame] = []
    if args.demo:
        frames.append(load_demo_to_dataframe())

    missing_tickers: list[str] = []
    if args.from_stocks:
        tickers = load_tickers_from_stocks(
            args.stocks_path,
            top_n=args.top_n,
            tickers=[t for t in args.tickers.split(",") if t.strip()] or None,
        )
        if not tickers:
            parser.error("No tickers found in stock CSV")
        ticker_news, missing_tickers = collect_news_for_tickers(
            tickers,
            sources=sources,
            max_items_per_source=args.max_items_per_source,
            sleep_seconds=args.sleep,
            finviz_elite=not args.finviz_free,
        )
        if not ticker_news.empty:
            frames.append(ticker_news)

    for url in args.rss:
        frames.append(fetch_rss_entries(url, max_items=args.max_items))

    if not frames:
        if args.from_stocks:
            raise RuntimeError(
                "No news collected for any ticker. "
                "Check your network, try --sources google,yahoo, or use more liquid tickers "
                "(e.g. --tickers NVDA,AAPL)."
            )
        parser.error("Provide --demo, --from-stocks, and/or one or more --rss URL")

    merged = pd.concat(frames, ignore_index=True)
    merged = merged.drop_duplicates(subset=["ticker", "url", "title"], keep="first")
    merged = merged[merged["title"].str.len() > 0].reset_index(drop=True)

    out = save_raw(merged, args.out)
    print(f"Wrote {len(merged)} rows to {out}")
    if missing_tickers:
        print(f"No news for {len(missing_tickers)} tickers: {', '.join(missing_tickers)}")


if __name__ == "__main__":
    main()
