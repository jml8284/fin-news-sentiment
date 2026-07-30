"""
Collect stock screener data from Finviz.

Modes:
  1) Finviz Elite export API (recommended for internship screener):
     python -m src.collect_stocks --elite --preset technical-gainers --top-n 20
  2) Free Finviz HTML screener scrape:
     python -m src.collect_stocks --signal most_active --top-n 20
  3) Offline demo:
     python -m src.collect_stocks --demo

Set FINVIZ_API_TOKEN in .env for --elite mode.
"""
from __future__ import annotations

import argparse
import io
import re
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.finviz_config import (
    PRESET_TECHNICAL_GAINERS,
    build_elite_export_url,
    build_elite_screener_url,
    build_elite_stock_url,
    get_api_token,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUT = RAW_DIR / "raw_stock_data.csv"
DEMO_CSV = RAW_DIR / "demo_mock_stocks.csv"

FINVIZ_BASE = "https://finviz.com/screener.ashx"
ROWS_PER_PAGE = 20
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

OUTPUT_COLUMNS = [
    "ticker",
    "company",
    "sector",
    "price",
    "change_pct",
    "volume",
    "market_cap",
    "pe",
    "source_url",
]

EXCHANGE_FILTERS = {
    "any": "",
    "nasdaq": "exch_nasd",
    "nyse": "exch_nyse",
    "amex": "exch_amex",
}

INDEX_FILTERS = {
    "any": "",
    "sp500": "idx_sp500",
    "nasdaq100": "idx_ndx",
    "dow": "idx_dji",
    "russell2000": "idx_rut",
}

SECTOR_FILTERS = {
    "any": "",
    "technology": "sec_technology",
    "healthcare": "sec_healthcare",
    "financial": "sec_financial",
    "energy": "sec_energy",
    "industrials": "sec_industrials",
    "consumer_cyclical": "sec_consumercyclical",
    "consumer_defensive": "sec_consumerdefensive",
    "communication": "sec_communicationservices",
    "basic_materials": "sec_basicmaterials",
    "real_estate": "sec_realestate",
    "utilities": "sec_utilities",
}

SIGNAL_FILTERS = {
    "none": "",
    "top_gainers": "ta_topgainers",
    "top_losers": "ta_toplosers",
    "most_active": "ta_mostactive",
    "most_volatile": "ta_mostvolatile",
    "unusual_volume": "ta_unusualvolume",
    "new_high": "ta_newhigh",
    "new_low": "ta_newlow",
}

ORDER_BY = {
    "volume": "-volume",
    "change": "-change",
    "price": "-price",
    "ticker": "ticker",
}

_PCT = re.compile(r"[^0-9.\-+]")


def _parse_float(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip().replace(",", "")
    if not s or s in {"-", "—", "–", "N/A", "n/a"}:
        return None
    try:
        return float(_PCT.sub("", s))
    except ValueError:
        return None


def _parse_int(value: object) -> int | None:
    parsed = _parse_float(value)
    if parsed is None:
        return None
    return int(parsed)


def build_filter_string(
    *,
    exchange: str = "any",
    index: str = "any",
    sector: str = "any",
    signal: str = "none",
    extra_filters: list[str] | None = None,
) -> str:
    parts: list[str] = []
    for key, mapping in (
        (exchange, EXCHANGE_FILTERS),
        (index, INDEX_FILTERS),
        (sector, SECTOR_FILTERS),
        (signal, SIGNAL_FILTERS),
    ):
        code = mapping.get(key, "")
        if code:
            parts.append(code)
    if extra_filters:
        parts.extend(f for f in extra_filters if f)
    return ",".join(parts)


def build_screener_url(
    *,
    start_row: int = 1,
    order: str = "volume",
    filters: str = "",
) -> str:
    params: dict[str, str | int] = {
        "v": 111,
        "o": ORDER_BY.get(order, ORDER_BY["volume"]),
        "r": start_row,
    }
    if filters:
        params["f"] = filters
    return f"{FINVIZ_BASE}?{urlencode(params)}"


def _fetch_with_requests(url: str, timeout: int) -> str:
    session = requests.Session()
    session.trust_env = False
    session.headers.update(DEFAULT_HEADERS)
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    if len(resp.text) < 1000:
        raise RuntimeError("Response too short; possible block page")
    return resp.text


def _fetch_with_cloudscraper(url: str, timeout: int) -> str:
    try:
        import cloudscraper
    except ImportError as exc:
        raise RuntimeError("cloudscraper is not installed") from exc

    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "darwin", "mobile": False}
    )
    scraper.trust_env = False
    resp = scraper.get(url, timeout=timeout)
    resp.raise_for_status()
    if len(resp.text) < 1000:
        raise RuntimeError("Response too short; possible block page")
    return resp.text


def fetch_html(url: str, *, timeout: int = 30, retries: int = 2) -> str:
    fetchers: list[tuple[str, Callable[[str, int], str]]] = [
        ("requests", _fetch_with_requests),
        ("cloudscraper", _fetch_with_cloudscraper),
    ]
    errors: list[str] = []

    for attempt in range(retries):
        for name, fetcher in fetchers:
            try:
                return fetcher(url, timeout)
            except Exception as exc:  # noqa: BLE001 - collect all fetch failures
                errors.append(f"{name} (attempt {attempt + 1}): {exc}")
        if attempt + 1 < retries:
            time.sleep(1.5 * (attempt + 1))

    raise RuntimeError("Failed to fetch Finviz page. " + " | ".join(errors))


def parse_overview_rows(html: str, source_url: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, object]] = []

    for table in soup.select("table.table-light"):
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 11:
                continue
            ticker = cells[1].get_text(strip=True)
            if not ticker or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", ticker):
                continue
            rows.append(
                {
                    "ticker": ticker,
                    "company": cells[2].get_text(strip=True),
                    "sector": cells[3].get_text(strip=True),
                    "price": _parse_float(cells[8].get_text(strip=True)),
                    "change_pct": _parse_float(cells[9].get_text(strip=True)),
                    "volume": _parse_int(cells[10].get_text(strip=True)),
                    "market_cap": cells[6].get_text(strip=True),
                    "pe": cells[7].get_text(strip=True),
                    "source_url": source_url,
                }
            )

    if rows:
        return rows

    # Fallback when markup changes: use pandas read_html on ticker links table.
    try:
        tables = pd.read_html(html)
    except ValueError:
        return []

    for table in tables:
        cols = {str(c).lower(): c for c in table.columns}
        ticker_col = None
        for candidate in ("ticker", "symbol"):
            if candidate in cols:
                ticker_col = cols[candidate]
                break
        if ticker_col is None:
            continue
        for _, row in table.iterrows():
            ticker = str(row[ticker_col]).strip()
            if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", ticker):
                continue
            rows.append(
                {
                    "ticker": ticker,
                    "company": str(row.get(cols.get("company", ticker_col), "")).strip(),
                    "sector": str(row.get(cols.get("sector", ticker_col), "")).strip(),
                    "price": _parse_float(row.get(cols.get("price", ticker_col))),
                    "change_pct": _parse_float(row.get(cols.get("change", ticker_col))),
                    "volume": _parse_int(row.get(cols.get("volume", ticker_col))),
                    "market_cap": str(row.get(cols.get("market cap", ticker_col), "")).strip(),
                    "pe": str(row.get(cols.get("p/e", ticker_col), "")).strip(),
                    "source_url": source_url,
                }
            )
        if rows:
            break
    return rows


def _find_column(df: pd.DataFrame, *names: str) -> str | None:
    lookup = {str(c).lower().strip(): c for c in df.columns}
    for name in names:
        key = name.lower()
        if key in lookup:
            return str(lookup[key])
    return None


def normalize_elite_export(
    df: pd.DataFrame,
    *,
    auth_token: str | None = None,
    export_url: str = "",
) -> pd.DataFrame:
    """Map Finviz Elite export CSV columns to project schema."""
    if df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    ticker_col = _find_column(df, "ticker", "symbol")
    if ticker_col is None:
        raise ValueError(f"Export CSV missing Ticker column. Got: {list(df.columns)}")

    rows: list[dict[str, object]] = []
    for _, raw in df.iterrows():
        ticker = str(raw[ticker_col]).strip().upper()
        if not ticker or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", ticker):
            continue

        company_col = _find_column(df, "company")
        sector_col = _find_column(df, "sector")
        price_col = _find_column(df, "price")
        change_col = _find_column(df, "change")
        volume_col = _find_column(df, "volume")
        mcap_col = _find_column(df, "market cap", "market_cap")
        pe_col = _find_column(df, "p/e", "pe")

        rows.append(
            {
                "ticker": ticker,
                "company": str(raw[company_col]).strip() if company_col else "",
                "sector": str(raw[sector_col]).strip() if sector_col else "",
                "price": _parse_float(raw[price_col]) if price_col else None,
                "change_pct": _parse_float(raw[change_col]) if change_col else None,
                "volume": _parse_int(raw[volume_col]) if volume_col else None,
                "market_cap": str(raw[mcap_col]).strip() if mcap_col else "",
                "pe": str(raw[pe_col]).strip() if pe_col else "",
                "source_url": build_elite_stock_url(ticker, auth_token),
            }
        )

    return pd.DataFrame(rows)[OUTPUT_COLUMNS]


def fetch_elite_export_csv(export_url: str, *, timeout: int = 30) -> pd.DataFrame:
    """Download screener results as CSV from Finviz Elite export endpoint."""
    session = requests.Session()
    session.trust_env = False
    session.headers.update(DEFAULT_HEADERS)
    resp = session.get(export_url, timeout=timeout)
    resp.raise_for_status()
    if not resp.content or len(resp.content) < 20:
        raise RuntimeError("Empty export response from Finviz Elite")
    return pd.read_csv(io.BytesIO(resp.content))


def collect_finviz_elite_export(
    *,
    auth_token: str,
    filters: str,
    order: str = "-change",
    filter_type: str = "3",
    view: int = 151,
    columns: str | None = None,
    after_row: int | None = None,
    top_n: int = 20,
) -> pd.DataFrame:
    """
    Collect stocks via Finviz Elite export API.

    Uses export URL (not the free HTML screener scrape).
    Each row's source_url points to the Elite stock chart page for that ticker.
    """
    export_url = build_elite_export_url(
        auth_token=auth_token,
        filters=filters,
        order=order,
        filter_type=filter_type,
        view=view,
        columns=columns,
        after_row=after_row,
    )
    raw = fetch_elite_export_csv(export_url)
    normalized = normalize_elite_export(raw, auth_token=auth_token, export_url=export_url)
    if top_n > 0:
        normalized = normalized.head(top_n).reset_index(drop=True)
    return normalized


def collect_finviz_stocks(
    *,
    top_n: int = 20,
    exchange: str = "any",
    index: str = "any",
    sector: str = "any",
    signal: str = "most_active",
    order: str = "volume",
    extra_filters: list[str] | None = None,
    sleep_seconds: float = 1.0,
) -> pd.DataFrame:
    if top_n <= 0:
        raise ValueError("top_n must be positive")

    filters = build_filter_string(
        exchange=exchange,
        index=index,
        sector=sector,
        signal=signal,
        extra_filters=extra_filters,
    )

    collected: list[dict[str, object]] = []
    seen: set[str] = set()
    start_row = 1

    while len(collected) < top_n:
        url = build_screener_url(start_row=start_row, order=order, filters=filters)
        html = fetch_html(url)
        page_rows = parse_overview_rows(html, url)
        if not page_rows:
            break

        for row in page_rows:
            ticker = str(row["ticker"])
            if ticker in seen:
                continue
            seen.add(ticker)
            collected.append(row)
            if len(collected) >= top_n:
                break

        if len(page_rows) < ROWS_PER_PAGE:
            break
        start_row += ROWS_PER_PAGE
        time.sleep(sleep_seconds)

    df = pd.DataFrame(collected)
    if df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    return df[OUTPUT_COLUMNS]


def load_demo_to_dataframe() -> pd.DataFrame:
    if not DEMO_CSV.exists():
        raise FileNotFoundError(f"Missing demo file: {DEMO_CSV}")
    df = pd.read_csv(DEMO_CSV)
    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[OUTPUT_COLUMNS]


def save_raw(df: pd.DataFrame, out_path: Path = DEFAULT_OUT) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect stock data from Finviz screener.")
    parser.add_argument("--demo", action="store_true", help="Use local demo_mock_stocks.csv (offline only)")
    parser.add_argument(
        "--elite",
        action="store_true",
        help="Use Finviz Elite export API (default when neither --demo nor --free-scrape)",
    )
    parser.add_argument(
        "--free-scrape",
        action="store_true",
        help="Use free Finviz HTML screener scrape (no Elite token)",
    )
    parser.add_argument(
        "--auth-token",
        default="",
        help="Finviz Elite API token (overrides FINVIZ_API_TOKEN env var)",
    )
    parser.add_argument(
        "--preset",
        choices=["technical-gainers"],
        default="technical-gainers",
        help="Elite screener preset matching professor filters",
    )
    parser.add_argument("--top-n", type=int, default=20, help="Number of tickers to collect")
    parser.add_argument(
        "--exchange",
        choices=sorted(EXCHANGE_FILTERS),
        default="any",
        help="Exchange filter",
    )
    parser.add_argument(
        "--index",
        choices=sorted(INDEX_FILTERS),
        default="any",
        help="Index filter",
    )
    parser.add_argument(
        "--sector",
        choices=sorted(SECTOR_FILTERS),
        default="any",
        help="Sector filter",
    )
    parser.add_argument(
        "--signal",
        choices=sorted(SIGNAL_FILTERS),
        default="most_active",
        help="Finviz signal preset",
    )
    parser.add_argument(
        "--order",
        choices=sorted(ORDER_BY),
        default="volume",
        help="Sort order for screener results",
    )
    parser.add_argument(
        "--filter",
        dest="extra_filters",
        action="append",
        default=[],
        metavar="CODE",
        help="Additional Finviz filter code (repeatable), e.g. geo_usa",
    )
    parser.add_argument("--sleep", type=float, default=1.0, help="Delay between page requests")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output CSV path")
    args = parser.parse_args()

    if args.demo:
        df = load_demo_to_dataframe()
    elif args.free_scrape:
        df = collect_finviz_stocks(
            top_n=args.top_n,
            exchange=args.exchange,
            index=args.index,
            sector=args.sector,
            signal=args.signal,
            order=args.order,
            extra_filters=args.extra_filters,
            sleep_seconds=args.sleep,
        )
    else:
        # Production default: Finviz Elite export
        token = get_api_token(args.auth_token or None)
        preset = PRESET_TECHNICAL_GAINERS
        extra = list(args.extra_filters)
        filters = preset["filters"]
        if extra:
            filters = ",".join([filters, *extra])
        df = collect_finviz_elite_export(
            auth_token=token,
            filters=filters,
            order=preset["order"],
            filter_type=str(preset["filter_type"]),
            view=int(preset["view"]),
            columns=preset.get("columns"),
            top_n=args.top_n,
        )
        screener_url = build_elite_screener_url(
            filters=preset["filters"],
            order=preset["order"],
            filter_type=str(preset["filter_type"]),
            view=int(preset["view"]),
        )
        print(f"Elite screener: {screener_url}")

    if df.empty:
        raise RuntimeError(
            "No stock rows collected. Check FINVIZ_API_TOKEN in .env or try --free-scrape / --demo."
        )

    out = save_raw(df, args.out)
    print(f"Wrote {len(df)} rows to {out}")


if __name__ == "__main__":
    main()
