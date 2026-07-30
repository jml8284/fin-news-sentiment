"""
Collect financial news per ticker from production sources.

Writes unified rows to data/raw/raw_news_data.csv

Production (default):
  python -m src.collect_news --from-stocks --top-n 20

Offline:
  python -m src.collect_news --demo
"""
from __future__ import annotations

import argparse
import logging
import re
import time
from datetime import datetime, timezone
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

NEWS_COLUMNS = ["ticker", "title", "summary", "published", "collected_at", "source", "url"]
SEC_PRESS_RSS = "https://www.sec.gov/news/pressreleases.rss"
RSS_SOURCE_FEEDS = {
    "globalwire": (
        "GlobeNewswire",
        "https://www.globenewswire.com/RssFeed/orgclass/1/feedTitle/GlobeNewswire%20-%20News%20about%20Public%20Companies",
    ),
    "prnewswire": ("PR Newswire", "https://www.prnewswire.com/rss/news-releases-list.rss"),
    "sec": ("SEC", SEC_PRESS_RSS),
    "fda": (
        "FDA",
        "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml",
    ),
}
AVAILABLE_SOURCES = ("google", "yahoo", "finviz", *RSS_SOURCE_FEEDS.keys())
_TAG_RE = re.compile(r"<[^>]+>")

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


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


def _mentions_ticker(title: str, summary: str, ticker: str) -> bool:
    symbol = ticker.upper().strip()
    if not symbol:
        return True
    text = f"{title} {summary}".upper()
    if f"${symbol}" in text:
        return True
    return re.search(rf"(?<![A-Z0-9]){re.escape(symbol)}(?![A-Z0-9])", text) is not None


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
                "collected_at": _utc_now(),
                "source": host,
                "url": link.strip(),
            }
        )

    return pd.DataFrame(rows)


def fetch_named_rss_news(
    ticker: str,
    *,
    source: str,
    max_items: int = 10,
) -> pd.DataFrame:
    label, feed_url = RSS_SOURCE_FEEDS[source]
    parsed = feedparser.parse(feed_url)
    rows: list[dict[str, str]] = []
    symbol = ticker.upper().strip()

    for entry in getattr(parsed, "entries", []):
        title = _strip_html(getattr(entry, "title", "") or "")
        summary = _strip_html(
            getattr(entry, "summary", "")
            or getattr(entry, "description", "")
            or ""
        )
        if symbol and not _mentions_ticker(title, summary, symbol):
            continue

        published = (getattr(entry, "published", "") or getattr(entry, "updated", "") or "").strip()
        link = (getattr(entry, "link", "") or "").strip()
        rows.append(
            {
                "ticker": symbol,
                "title": title,
                "summary": summary,
                "published": published,
                "collected_at": _utc_now(),
                "source": label,
                "url": link,
            }
        )
        if len(rows) >= max_items:
            break

    return pd.DataFrame(rows, columns=NEWS_COLUMNS)


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


def fetch_sec_news(ticker: str, *, max_items: int = 10) -> pd.DataFrame:
    """
    Filter SEC press release RSS for items mentioning the ticker symbol.
    Many small tickers may return zero rows (expected).
    """
    return fetch_named_rss_news(ticker, source="sec", max_items=max_items)


def _find_finviz_news_table(soup: BeautifulSoup) -> object | None:
    table = soup.select_one("table.fullview-news-outer")
    if table is not None:
        return table
    table = soup.find("table", id="news-table")
    if table is not None:
        return table
    for candidate in soup.select("table.news-table"):
        return candidate
    return None


def _normalize_finviz_href(href: str) -> str:
    href = (href or "").strip()
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return "https://finviz.com" + href
    return href


def parse_finviz_news_html(
    html: str,
    ticker: str,
    *,
    source_label: str = "Finviz Elite",
    max_items: int = 0,
) -> pd.DataFrame:
    """Parse Finviz quote/stock page HTML into news rows."""
    soup = BeautifulSoup(html, "html.parser")
    table = _find_finviz_news_table(soup)
    if table is None:
        return pd.DataFrame(columns=NEWS_COLUMNS)

    rows: list[dict[str, str]] = []
    date_prefix = ""
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        time_cell = cells[0].get_text(" ", strip=True)
        link = cells[1].find("a")
        if link is None:
            continue
        title = link.get_text(strip=True)
        if not title:
            continue
        href = _normalize_finviz_href(link.get("href", ""))

        if time_cell:
            first_token = time_cell.split()[0]
            if "-" in first_token:
                date_prefix = first_token
                published = time_cell
            elif date_prefix:
                published = f"{date_prefix} {time_cell}".strip()
            else:
                published = time_cell
        else:
            published = date_prefix

        rows.append(
            {
                "ticker": ticker.upper(),
                "title": title,
                "summary": "",
                "published": published,
                "collected_at": _utc_now(),
                "source": source_label,
                "url": href,
            }
        )
        if max_items > 0 and len(rows) >= max_items:
            break

    return pd.DataFrame(rows)


def _finviz_news_page_urls(ticker: str, token: str | None, *, use_elite: bool) -> list[str]:
    sym = quote_plus(ticker.upper())
    if use_elite and token:
        return [
            build_elite_stock_url(ticker, token),
            f"https://elite.finviz.com/quote.ashx?t={sym}&auth={token}",
        ]
    if use_elite:
        return [build_elite_stock_url(ticker, None)]
    return [f"https://finviz.com/quote.ashx?t={sym}"]


def fetch_finviz_news(
    ticker: str,
    *,
    max_items: int = 0,
    auth_token: str | None = None,
    use_elite: bool = True,
) -> pd.DataFrame:
    """
    Fetch news from Finviz quote/stock page (live HTML scrape).

    max_items=0 means no cap (collect every row Finviz returns on the page).
    """
    token = auth_token
    if use_elite and token is None:
        try:
            token = get_api_token(None)
        except RuntimeError:
            token = None

    source_label = "Finviz Elite" if use_elite else "Finviz"
    rows: list[dict[str, str]] = []
    last_html_len = 0

    for url in _finviz_news_page_urls(ticker, token, use_elite=use_elite):
        try:
            html = fetch_html(url)
            last_html_len = len(html)
            parsed = parse_finviz_news_html(
                html,
                ticker,
                source_label=source_label,
                max_items=max_items if max_items > 0 else 0,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Finviz news fetch failed for %s (%s): %s", ticker, url, exc)
            continue
        if not parsed.empty:
            return parsed
        if max_items > 0 and len(rows) >= max_items:
            break

    if not rows and last_html_len > 0:
        logger.warning(
            "Finviz news table not found for %s (html bytes=%s). Check Elite page markup.",
            ticker,
            last_html_len,
        )

    return pd.DataFrame(rows, columns=NEWS_COLUMNS) if rows else pd.DataFrame(columns=NEWS_COLUMNS)


def collect_news_for_ticker(
    ticker: str,
    *,
    sources: list[str],
    max_items_per_source: int = 10,
    finviz_max_items: int = 0,
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
    for source_name in RSS_SOURCE_FEEDS:
        fetchers[source_name] = (
            lambda t, max_items, source_name=source_name: fetch_named_rss_news(
                t,
                source=source_name,
                max_items=max_items,
            )
        )

    for source in sources:
        fetcher = fetchers.get(source)
        if fetcher is None:
            continue
        try:
            limit = finviz_max_items if source == "finviz" else max_items_per_source
            df = fetcher(ticker, max_items=limit)
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
    finviz_max_items: int = 0,
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
            finviz_max_items=finviz_max_items,
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
    parser.add_argument("--demo", action="store_true", help="Load rows from demo_mock_news.csv (offline only)")
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
        default="finviz,google,yahoo,sec",
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
        help="Max items per ticker for Google/Yahoo/SEC",
    )
    parser.add_argument(
        "--finviz-max-items",
        type=int,
        default=0,
        help="Max Finviz quote-page news rows per ticker (0 = no cap, collect all on page)",
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

    if not args.demo and not args.from_stocks and not args.rss:
        args.from_stocks = True

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
            finviz_max_items=args.finviz_max_items,
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
