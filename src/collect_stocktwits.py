"""
Fetch Stocktwits symbol streams for dashboard social sourcing.

Primary: stocktwits.com symbol pages fetched with curl_cffi browser impersonation.
The public api.stocktwits.com endpoint is disabled by default and only used when
STOCKTWITS_USE_PUBLIC_API=1 is explicitly set.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

STOCKTWITS_STREAM_URL = "https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
STOCKTWITS_SYMBOL_JSON_URL = "https://stocktwits.com/symbol/{symbol}.json"
STOCKTWITS_SYMBOL_PAGE = "https://stocktwits.com/symbol/{symbol}"
STOCKTWITS_SENTIMENT_DETAIL_URL = "https://api-gw-prd.stocktwits.com/sentiment-api/v2/{symbol}/detail"
STOCKTWITS_PRICE_CHART_URL = "https://ql.stocktwits.com/v2/prices/chart"
STOCKTWITS_QUOTE_STREAM_URL = "wss://ql-websocket.stocktwits.com/v2/stream"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://stocktwits.com/",
}

MESSAGE_ID_RE = re.compile(r"^message-(\d+)$")

_rate_lock = threading.Lock()
_last_request_at = 0.0

MESSAGE_COLUMNS = [
    "ticker",
    "title",
    "summary",
    "published",
    "collected_at",
    "source",
    "url",
    "stocktwits_sentiment",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _message_url(symbol: str, message_id: int | str) -> str:
    return f"https://stocktwits.com/symbol/{symbol.upper()}/message/{message_id}"


def _parse_native_sentiment(entities: object) -> str:
    if not isinstance(entities, dict):
        return ""
    sentiment = entities.get("sentiment")
    if not isinstance(sentiment, dict):
        return ""
    return str(sentiment.get("basic", "")).strip()


def _get_access_token(explicit: str | None = None) -> str | None:
    token = (explicit or os.getenv("STOCKTWITS_ACCESS_TOKEN", "")).strip()
    return token or None


def _use_web_only() -> bool:
    return os.getenv("STOCKTWITS_USE_WEB", "").strip().lower() in {"1", "true", "yes"}


def _use_public_api() -> bool:
    return os.getenv("STOCKTWITS_USE_PUBLIC_API", "0").strip().lower() in {"1", "true", "yes"}


def _web_fallback_enabled() -> bool:
    return os.getenv("STOCKTWITS_WEB_FALLBACK", "0").strip().lower() in {"1", "true", "yes"}


def _curl_impersonate_enabled() -> bool:
    return os.getenv("STOCKTWITS_USE_CURL_IMPERSONATE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def _curl_impersonate_profile() -> str:
    return os.getenv("STOCKTWITS_CURL_IMPERSONATE_PROFILE", "chrome124").strip() or "chrome124"


def stocktwits_transport_label() -> str:
    if _curl_impersonate_enabled():
        return f"stocktwits.com via curl_cffi ({_curl_impersonate_profile()}); requests/cloudscraper fallback"
    return "requests; cloudscraper fallback on connection errors"


def _min_request_interval_sec() -> float:
    try:
        return max(float(os.getenv("STOCKTWITS_MIN_INTERVAL_SEC", "5")), 0.0)
    except ValueError:
        return 5.0


def _throttle_before_request() -> None:
    """Space out Stocktwits HTTP calls (professor / API rate-limit friendly)."""
    interval = _min_request_interval_sec()
    if interval <= 0:
        return
    global _last_request_at
    with _rate_lock:
        now = time.monotonic()
        wait = interval - (now - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


def _fetch_url(url: str, *, timeout: int) -> tuple[int, str, str]:
    """Return (status_code, body_text, content_type). Tries curl-impersonate first."""
    _throttle_before_request()

    if _curl_impersonate_enabled():
        try:
            from curl_cffi import requests as curl_requests

            resp = curl_requests.get(
                url,
                headers=BROWSER_HEADERS,
                impersonate=_curl_impersonate_profile(),
                timeout=timeout,
            )
            return resp.status_code, resp.text or "", resp.headers.get("Content-Type", "")
        except Exception as exc:  # noqa: BLE001
            logger.debug("Stocktwits curl_cffi failed: %s", exc)

    session = requests.Session()
    session.trust_env = False
    session.headers.update(BROWSER_HEADERS)

    try:
        resp = session.get(url, timeout=timeout)
        return resp.status_code, resp.text or "", resp.headers.get("Content-Type", "")
    except requests.RequestException as exc:
        logger.debug("Stocktwits requests failed: %s", exc)

    try:
        import cloudscraper

        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )
        scraper.trust_env = False
        resp = scraper.get(url, timeout=timeout)
        return resp.status_code, resp.text or "", resp.headers.get("Content-Type", "")
    except Exception as exc:  # noqa: BLE001
        logger.debug("Stocktwits cloudscraper failed: %s", exc)
        return 0, "", ""


def _fetch_symbol_page_html(symbol: str, *, timeout: int) -> str:
    """Fetch Stocktwits symbol page HTML (requests → cloudscraper)."""
    _throttle_before_request()
    url = STOCKTWITS_SYMBOL_PAGE.format(symbol=symbol.upper())
    errors: list[str] = []

    for name, fetcher in (
        ("requests", lambda u, t: requests.Session()),
        ("cloudscraper", None),
    ):
        try:
            if name == "requests":
                session = requests.Session()
                session.trust_env = False
                session.headers.update(BROWSER_HEADERS)
                resp = session.get(url, timeout=timeout)
            else:
                import cloudscraper

                session = cloudscraper.create_scraper(
                    browser={"browser": "chrome", "platform": "darwin", "mobile": False}
                )
                session.trust_env = False
                resp = session.get(url, timeout=timeout, headers=BROWSER_HEADERS)
            resp.raise_for_status()
            html = resp.text or ""
            if len(html) < 1000:
                raise RuntimeError("response too short (possible block page)")
            if "RichTextMessage_body" not in html and "__NEXT_DATA__" not in html:
                raise RuntimeError("page missing message content (Cloudflare block?)")
            return html
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}")

    raise RuntimeError("Failed to fetch Stocktwits symbol page. " + " | ".join(errors))


def _fetch_symbol_page_html(symbol: str, *, timeout: int) -> str:
    """Fetch Stocktwits symbol page HTML via curl impersonation first."""
    url = STOCKTWITS_SYMBOL_PAGE.format(symbol=symbol.upper())
    status, html, content_type = _fetch_url(url, timeout=timeout)
    if status != 200:
        preview = (html or "")[:120].replace("\n", " ")
        raise RuntimeError(f"HTTP {status} from Stocktwits web page: {preview}")
    if "text/html" not in content_type.lower() and "<html" not in html[:500].lower():
        raise RuntimeError(f"unexpected content type from Stocktwits page: {content_type or 'unknown'}")
    if len(html) < 1000:
        raise RuntimeError("response too short (possible block page)")
    if "RichTextMessage_body" not in html and "__NEXT_DATA__" not in html:
        raise RuntimeError("page missing message content (possible block page or changed markup)")
    return html


def _allow_sample() -> bool:
    return os.getenv("STOCKTWITS_ALLOW_SAMPLE", "0").strip().lower() in {"1", "true", "yes"}


SAMPLE_PATH = PROJECT_ROOT / "data" / "samples" / "stocktwits_messages.json"


def _load_sample_messages(symbol: str, *, max_items: int) -> pd.DataFrame:
    """Load bundled sample messages when live Stocktwits is blocked."""
    if not SAMPLE_PATH.is_file():
        return pd.DataFrame(columns=MESSAGE_COLUMNS)

    try:
        raw = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return pd.DataFrame(columns=MESSAGE_COLUMNS)

    if not isinstance(raw, list):
        return pd.DataFrame(columns=MESSAGE_COLUMNS)

    from src.news_filters import utc_today

    today = utc_today()
    collected = _utc_now()
    rows: list[dict[str, str]] = []

    for item in raw:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).upper().strip()
        if ticker != symbol.upper():
            continue
        body = str(item.get("title", "")).strip()
        if not body:
            continue
        offset = int(item.get("published_offset_days", 0))
        published_dt = datetime.combine(
            today - timedelta(days=max(offset, 0)),
            datetime.min.time(),
            tzinfo=timezone.utc,
        ).replace(hour=12, minute=0, second=0)
        message_id = str(item.get("message_id", "")).strip()
        rows.append(
            {
                "ticker": ticker,
                "title": body[:500],
                "summary": "",
                "published": published_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "collected_at": collected,
                "source": "Stocktwits (sample)",
                "url": _message_url(ticker, message_id) if message_id else f"https://stocktwits.com/symbol/{ticker}",
                "stocktwits_sentiment": str(item.get("stocktwits_sentiment", "")).strip(),
            }
        )

    if max_items > 0:
        rows = rows[:max_items]

    if not rows:
        # Generic demo lines for tickers not in the sample file (live fetch blocked).
        templates = [
            ("Bullish on ${t} — momentum holding above recent support.", "Bullish", 1),
            ("Watching ${t} for a breakout; volume still light.", "", 3),
        ]
        for body_tpl, sent, offset in templates:
            published_dt = datetime.combine(
                today - timedelta(days=offset),
                datetime.min.time(),
                tzinfo=timezone.utc,
            ).replace(hour=10, minute=30, second=0)
            rows.append(
                {
                    "ticker": symbol.upper(),
                    "title": body_tpl.replace("${t}", f"${symbol.upper()}")[:500],
                    "summary": "",
                    "published": published_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "collected_at": collected,
                    "source": "Stocktwits (sample)",
                    "url": f"https://stocktwits.com/symbol/{symbol.upper()}",
                    "stocktwits_sentiment": sent,
                }
            )
            if max_items > 0 and len(rows) >= max_items:
                break

    return pd.DataFrame(rows, columns=MESSAGE_COLUMNS) if rows else pd.DataFrame(columns=MESSAGE_COLUMNS)


def _fetch_via_sample(symbol: str, *, max_items: int) -> tuple[pd.DataFrame, str | None]:
    df = _load_sample_messages(symbol, max_items=max_items)
    if df.empty:
        return df, f"no sample messages for {symbol.upper()}"
    return df, None


def _sentiment_from_message_node(node) -> str:
    bull = node.select_one('[data-testid="bullish-button"]')
    bear = node.select_one('[data-testid="bearish-button"]')
    if bull and bull.get("aria-pressed") == "true":
        return "Bullish"
    if bear and bear.get("aria-pressed") == "true":
        return "Bearish"
    return ""


def parse_stocktwits_symbol_html(html: str, symbol: str, *, max_items: int = 30) -> pd.DataFrame:
    """Parse messages embedded in stocktwits.com/symbol/{ticker} HTML."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, str]] = []
    collected = _utc_now()
    seen_ids: set[str] = set()

    for node in soup.select("[data-testid]"):
        test_id = str(node.get("data-testid", "")).strip()
        match = MESSAGE_ID_RE.match(test_id)
        if not match:
            continue
        message_id = match.group(1)
        if message_id in seen_ids:
            continue

        body_el = node.select_one('[class*="RichTextMessage_body"]')
        body = body_el.get_text("\n", strip=True) if body_el else ""
        if not body:
            continue

        time_el = node.select_one("time[datetime]")
        published = time_el.get("datetime", "").strip() if time_el else ""

        seen_ids.add(message_id)
        rows.append(
            {
                "ticker": symbol.upper(),
                "title": body[:500],
                "summary": "",
                "published": published,
                "collected_at": collected,
                "source": "Stocktwits (web)",
                "url": _message_url(symbol, message_id),
                "stocktwits_sentiment": _sentiment_from_message_node(node),
            }
        )
        if max_items > 0 and len(rows) >= max_items:
            break

    return pd.DataFrame(rows, columns=MESSAGE_COLUMNS) if rows else pd.DataFrame(columns=MESSAGE_COLUMNS)


def _fetch_via_web(symbol: str, *, max_items: int, timeout: int) -> tuple[pd.DataFrame, str | None]:
    try:
        html = _fetch_symbol_page_html(symbol, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return pd.DataFrame(columns=MESSAGE_COLUMNS), f"web scrape failed: {exc}"

    df = parse_stocktwits_symbol_html(html, symbol, max_items=max_items)
    if df.empty:
        return df, "web page loaded but no messages parsed"
    return df, None


def _fetch_via_frontend_json(symbol: str, *, max_items: int, timeout: int) -> tuple[pd.DataFrame, str | None]:
    """Fetch the symbol feed JSON request used by stocktwits.com pages."""
    candidates = [
        f"{STOCKTWITS_STREAM_URL.format(symbol=symbol)}?filter=top&limit={max_items}",
        STOCKTWITS_STREAM_URL.format(symbol=symbol),
        f"{STOCKTWITS_SYMBOL_JSON_URL.format(symbol=symbol)}?filter=top&limit={max_items}",
        STOCKTWITS_SYMBOL_JSON_URL.format(symbol=symbol),
    ]
    errors: list[str] = []
    for url in candidates:
        status, text, content_type = _fetch_url(url, timeout=timeout)
        if status != 200:
            preview = (text or "")[:90].replace("\n", " ")
            errors.append(f"{url}: HTTP {status} {preview}")
            continue
        stripped = (text or "").strip()
        if not stripped or stripped.startswith("<!") or "text/html" in content_type.lower():
            errors.append(f"{url}: HTML/empty response")
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            errors.append(f"{url}: invalid JSON {exc}")
            continue

        df = _parse_messages(payload, symbol, max_items=max_items)
        if not df.empty:
            return df, None
        errors.append(f"{url}: JSON had no messages")

    return pd.DataFrame(columns=MESSAGE_COLUMNS), "; ".join(errors[-2:]) if errors else "no frontend json candidates"


def fetch_stocktwits_sentiment_detail(
    ticker: str,
    *,
    timeout: int = 20,
    end: datetime | None = None,
) -> tuple[dict, str | None]:
    """Fetch Stocktwits frontend sentiment/message-volume detail via curl impersonation."""
    symbol = str(ticker).upper().strip()
    if not symbol:
        return {}, "empty ticker"

    end_dt = end or datetime.now(timezone.utc)
    end_value = end_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    url = f"{STOCKTWITS_SENTIMENT_DETAIL_URL.format(symbol=symbol)}?end={end_value}"
    status, text, content_type = _fetch_url(url, timeout=timeout)

    if status != 200:
        preview = (text or "")[:120].replace("\n", " ")
        return {}, f"Stocktwits sentiment gateway HTTP {status}: {preview}"
    if "json" not in content_type.lower() and not text.strip().startswith("{"):
        return {}, f"Stocktwits sentiment gateway returned non-JSON content: {content_type or 'unknown'}"
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return {}, f"invalid sentiment gateway JSON: {exc}"

    data = payload.get("data")
    if not isinstance(data, dict):
        return {}, "sentiment gateway response missing data"
    return data, None


def fetch_stocktwits_chart_data(
    ticker: str,
    *,
    zoom: str = "1d",
    timeout: int = 20,
) -> tuple[pd.DataFrame, str | None]:
    """Fetch the Stocktwits chart time series used by the symbol page."""
    symbol = str(ticker).upper().strip()
    if not symbol:
        return pd.DataFrame(), "empty ticker"

    params = urlencode(
        {
            "symbol": symbol,
            "zoom": str(zoom).lower(),
            "extended-granularity": "true",
        }
    )
    url = f"{STOCKTWITS_PRICE_CHART_URL}?{params}"
    status, text, content_type = _fetch_url(url, timeout=timeout)
    if status != 200:
        preview = (text or "")[:120].replace("\n", " ")
        return pd.DataFrame(), f"Stocktwits chart HTTP {status}: {preview}"
    if "json" not in content_type.lower() and not (text or "").strip().startswith("{"):
        return pd.DataFrame(), f"Stocktwits chart returned non-JSON content: {content_type or 'unknown'}"
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return pd.DataFrame(), f"invalid Stocktwits chart JSON: {exc}"

    points = payload.get("data")
    if not isinstance(points, list):
        return pd.DataFrame(), "Stocktwits chart response missing data points"

    rows: list[dict[str, object]] = []
    for item in points:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "ticker": symbol,
                "datetime": item.get("start_time"),
                "open": item.get("open"),
                "high": item.get("high"),
                "low": item.get("low"),
                "close": item.get("close"),
                "volume": item.get("volume"),
                "sentiment_score": item.get("sentiment_normalized"),
                "message_volume_score": item.get("message_volume_normalized"),
                "watchers_count": item.get("watchers_count"),
                "session_type": item.get("session_type"),
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame, "Stocktwits chart returned no rows"
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce", utc=True)
    for col in (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "sentiment_score",
        "message_volume_score",
        "watchers_count",
    ):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.dropna(subset=["datetime", "close"]).sort_values("datetime").reset_index(drop=True)
    if frame.empty:
        return frame, "Stocktwits chart rows had no parseable datetime/close"
    return frame, None


def _quote_payload_to_row(symbol: str, payload: dict[str, object]) -> dict[str, object] | None:
    if str(payload.get("symbol", "")).upper() != symbol.upper():
        return None
    combined = payload.get("combined")
    extended = payload.get("extended_hours")
    if not isinstance(combined, dict):
        combined = {}
    if not isinstance(extended, dict):
        extended = {}

    price = combined.get("price")
    timestamp = combined.get("timestamp")
    session_type = extended.get("session_type") or "REGULAR"
    if price is None:
        price = extended.get("price")
        timestamp = extended.get("timestamp")
        session_type = extended.get("session_type") or session_type
    if price is None:
        price = payload.get("last")
        timestamp = payload.get("timestamp")
    if price is None or timestamp is None:
        return None

    return {
        "ticker": symbol.upper(),
        "datetime": timestamp,
        "open": payload.get("open"),
        "high": payload.get("high"),
        "low": payload.get("low"),
        "close": price,
        "volume": payload.get("volume"),
        "sentiment_score": pd.NA,
        "message_volume_score": pd.NA,
        "watchers_count": pd.NA,
        "session_type": session_type,
        "source": "Stocktwits websocket quote",
    }


async def _fetch_stocktwits_realtime_quotes_async(
    symbol: str,
    *,
    duration_seconds: float,
    timeout: int,
) -> list[dict[str, object]]:
    import websockets

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en,zh;q=0.9,zh-CN;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    config = {
        "message_type": "NEW_CONFIG",
        "payload": {
            "symbols": [symbol.upper()],
            "chart_symbols": [symbol.upper()],
            "symbol_stream_id": 37011,
        },
    }
    rows: list[dict[str, object]] = []
    deadline = time.monotonic() + max(1.0, float(duration_seconds))
    async with websockets.connect(
        STOCKTWITS_QUOTE_STREAM_URL,
        origin="https://stocktwits.com",
        additional_headers=headers,
        compression="deflate",
        open_timeout=timeout,
    ) as ws:
        await ws.send(json.dumps(config))
        while time.monotonic() < deadline:
            wait_for = max(0.5, min(5.0, deadline - time.monotonic()))
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=wait_for)
            except asyncio.TimeoutError:
                continue
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue
            message_type = data.get("message_type")
            payload = data.get("payload")
            if message_type == "QUOTE" and isinstance(payload, dict):
                row = _quote_payload_to_row(symbol, payload)
                if row:
                    rows.append(row)
            elif message_type == "QUOTE_BATCH" and isinstance(payload, dict):
                quote = payload.get(symbol.upper())
                if isinstance(quote, dict):
                    row = _quote_payload_to_row(symbol, quote)
                    if row:
                        rows.append(row)
    return rows


def fetch_stocktwits_realtime_quotes(
    ticker: str,
    *,
    duration_seconds: float = 6.0,
    timeout: int = 15,
) -> tuple[pd.DataFrame, str | None]:
    """Collect live quote ticks from the Stocktwits websocket for a short window."""
    symbol = str(ticker).upper().strip()
    if not symbol:
        return pd.DataFrame(), "empty ticker"
    try:
        rows = asyncio.run(
            _fetch_stocktwits_realtime_quotes_async(
                symbol,
                duration_seconds=duration_seconds,
                timeout=timeout,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return pd.DataFrame(), f"Stocktwits websocket unavailable: {exc}"

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame, "Stocktwits websocket returned no quote rows"
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce", utc=True)
    for col in ("open", "high", "low", "close", "volume"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.dropna(subset=["datetime", "close"]).sort_values("datetime").reset_index(drop=True)
    if frame.empty:
        return frame, "Stocktwits websocket rows had no parseable datetime/close"
    return frame, None


def _parse_messages(payload: dict, symbol: str, *, max_items: int) -> pd.DataFrame:
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return pd.DataFrame(columns=MESSAGE_COLUMNS)

    rows: list[dict[str, str]] = []
    collected = _utc_now()
    limit = max_items if max_items > 0 else len(messages)

    for item in messages[:limit]:
        if not isinstance(item, dict):
            continue
        body = str(item.get("body", "")).strip()
        if not body:
            continue
        message_id = item.get("id", "")
        created = str(item.get("created_at", "")).strip()
        native = _parse_native_sentiment(item.get("entities"))
        rows.append(
            {
                "ticker": symbol,
                "title": body[:500],
                "summary": "",
                "published": created,
                "collected_at": collected,
                "source": "Stocktwits",
                "url": _message_url(symbol, message_id) if message_id else f"https://stocktwits.com/symbol/{symbol}",
                "stocktwits_sentiment": native,
            }
        )

    return pd.DataFrame(rows, columns=MESSAGE_COLUMNS) if rows else pd.DataFrame(columns=MESSAGE_COLUMNS)


def fetch_stocktwits_messages(
    ticker: str,
    *,
    max_items: int = 30,
    timeout: int = 20,
    access_token: str | None = None,
) -> pd.DataFrame:
    """Return recent Stocktwits messages (empty DataFrame on failure)."""
    df, _err = fetch_stocktwits_messages_with_error(
        ticker,
        max_items=max_items,
        timeout=timeout,
        access_token=access_token,
    )
    return df


def fetch_stocktwits_messages_with_error(
    ticker: str,
    *,
    max_items: int = 30,
    timeout: int = 20,
    access_token: str | None = None,
) -> tuple[pd.DataFrame, str | None]:
    """Return (messages, error_message). error_message is None on success with rows."""
    symbol = str(ticker).upper().strip()
    if not symbol:
        return pd.DataFrame(columns=MESSAGE_COLUMNS), "empty ticker"

    frontend_df, frontend_err = _fetch_via_frontend_json(symbol, max_items=max_items, timeout=timeout)
    if not frontend_df.empty:
        return frontend_df, None

    if _use_web_only() or not _use_public_api():
        df, err = _fetch_via_web(symbol, max_items=max_items, timeout=timeout)
        if not df.empty:
            return df, None
        if _allow_sample():
            df, sample_err = _fetch_via_sample(symbol, max_items=max_items)
            if not df.empty:
                return df, None
            err = f"{err}; sample: {sample_err}"
        if not _use_public_api():
            return (
                pd.DataFrame(columns=MESSAGE_COLUMNS),
                f"frontend json failed ({frontend_err}); web/curl-impersonate scrape failed ({err}); public API disabled",
            )
        return pd.DataFrame(columns=MESSAGE_COLUMNS), err

    url = STOCKTWITS_STREAM_URL.format(symbol=symbol)
    token = _get_access_token(access_token)
    if token:
        url = f"{url}?access_token={token}"

    status, text, content_type = _fetch_url(url, timeout=timeout)
    api_failed = status in {0, 403, 429} or (
        status == 200 and (text.strip().startswith("<!") or "text/html" in content_type.lower())
    )

    if not api_failed and status == 200:
        stripped = text.strip()
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            api_failed = True
            api_err = f"invalid JSON: {exc}"
        else:
            if isinstance(payload, dict) and payload.get("errors"):
                err = payload["errors"][0] if payload["errors"] else {}
                msg = err.get("message", "unknown API error") if isinstance(err, dict) else str(err)
                return pd.DataFrame(columns=MESSAGE_COLUMNS), msg

            df = _parse_messages(payload, symbol, max_items=max_items)
            if df.empty:
                return df, "no messages for this symbol"
            return df, None
    else:
        if status == 403:
            if "cloudflare" in text.lower() or "sorry, you have been blocked" in text.lower():
                api_err = "403 Forbidden (Cloudflare/WAF block)"
            else:
                api_err = "403 Forbidden (API access denied)"
        elif status == 429:
            api_err = "429 rate limit"
        elif status == 0:
            api_err = "network error"
        elif status != 200:
            api_err = f"HTTP {status}"
        else:
            api_err = "HTML instead of JSON"

    if _web_fallback_enabled():
        df, web_err = _fetch_via_web(symbol, max_items=max_items, timeout=timeout)
        if not df.empty:
            return df, None
    else:
        web_err = "web fallback disabled (set STOCKTWITS_WEB_FALLBACK=1 to enable)"

    if _allow_sample():
        df, sample_err = _fetch_via_sample(symbol, max_items=max_items)
        if not df.empty:
            return df, None
        web_err = f"{web_err}; sample: {sample_err}"

    return (
        pd.DataFrame(columns=MESSAGE_COLUMNS),
        f"API blocked ({api_err}); web fallback failed ({web_err})",
    )
