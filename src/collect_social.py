"""Fetch social posts without depending on Stocktwits.

Primary source: Bluesky public XRPC search via ``api.bsky.app``.
Reddit remains available as an optional fallback/reference source, but Reddit
currently blocks many proxy/network-policy requests.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
from dotenv import load_dotenv

from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

SOCIAL_COLUMNS = [
    "ticker",
    "title",
    "summary",
    "published",
    "collected_at",
    "source",
    "url",
    "social_sentiment",
]

REDDIT_BASE_URL = "https://old.reddit.com"
BLUESKY_SEARCH_URL = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"
DEFAULT_SUBREDDITS = ("wallstreetbets", "stocks", "StockMarket", "pennystocks")

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_rate_lock = threading.Lock()
_last_request_at = 0.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _social_source() -> str:
    return os.getenv("SOCIAL_SOURCE", "bluesky").strip().lower() or "bluesky"


def _proxy_url() -> str:
    return os.getenv("SOCIAL_PROXY_URL", "").strip()


def _request_proxies() -> dict[str, str] | None:
    proxy = _proxy_url()
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


def _subreddits() -> list[str]:
    raw = os.getenv("SOCIAL_REDDIT_SUBREDDITS", "")
    values = [s.strip().strip("/").replace("r/", "") for s in raw.split(",") if s.strip()]
    return values or list(DEFAULT_SUBREDDITS)


def _max_subreddits(default: int = 2) -> int:
    try:
        return max(int(os.getenv("SOCIAL_REDDIT_MAX_SUBREDDITS", str(default))), 1)
    except ValueError:
        return default


def _curl_impersonate_profile() -> str:
    return os.getenv("SOCIAL_CURL_IMPERSONATE_PROFILE", "chrome124").strip() or "chrome124"


def _curl_impersonate_enabled() -> bool:
    return os.getenv("SOCIAL_USE_CURL_IMPERSONATE", "1").strip().lower() not in {"0", "false", "no"}


def _allow_sample() -> bool:
    return os.getenv("SOCIAL_ALLOW_SAMPLE", "1").strip().lower() not in {"0", "false", "no"}


def _min_request_interval_sec() -> float:
    try:
        return max(float(os.getenv("SOCIAL_MIN_INTERVAL_SEC", "2")), 0.0)
    except ValueError:
        return 2.0


def _throttle_before_request() -> None:
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
            logger.debug("Reddit curl_cffi failed: %s", exc)

    session = requests.Session()
    session.trust_env = False
    session.headers.update(BROWSER_HEADERS)
    try:
        resp = session.get(url, timeout=timeout)
        return resp.status_code, resp.text or "", resp.headers.get("Content-Type", "")
    except requests.RequestException as exc:
        logger.debug("Reddit requests failed: %s", exc)
        return 0, "", ""


def _reddit_search_url(subreddit: str, ticker: str, *, limit: int) -> str:
    query = f"${ticker.upper()} OR {ticker.upper()}"
    params = {
        "q": query,
        "restrict_sr": "1",
        "sort": "new",
        "t": "month",
        "limit": str(limit),
        "raw_json": "1",
    }
    return f"{REDDIT_BASE_URL}/r/{subreddit}/search.json?{urllib.parse.urlencode(params)}"


def _content_hash(source: str, post_id: str, title: str, text: str) -> str:
    return hashlib.sha1(f"{source}:{post_id}:{title}:{text}".encode("utf-8")).hexdigest()[:16]


def _clean_text(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _published_from_utc(value: object) -> str:
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _reddit_permalink(permalink: str) -> str:
    if not permalink:
        return ""
    if permalink.startswith("http"):
        return permalink
    return f"https://www.reddit.com{permalink}"


def _sentiment_hint(title: str, text: str) -> str:
    body = f"{title} {text}".lower()
    bullish = ("bullish", "breakout", "moon", "buy", "calls", "upside", "rally", "squeeze")
    bearish = ("bearish", "sell", "puts", "downside", "dump", "short", "crash", "bagholder")
    bull_hits = sum(1 for token in bullish if token in body)
    bear_hits = sum(1 for token in bearish if token in body)
    if bull_hits > bear_hits:
        return "Bullish"
    if bear_hits > bull_hits:
        return "Bearish"
    return ""


def _bluesky_url_from_uri(uri: str, handle: str) -> str:
    parts = str(uri or "").rsplit("/", 1)
    if len(parts) != 2 or not handle:
        return ""
    return f"https://bsky.app/profile/{handle}/post/{parts[1]}"


def _fetch_bluesky_json(query: str, *, limit: int, timeout: int) -> tuple[int, dict | None, str]:
    _throttle_before_request()
    session = requests.Session()
    session.trust_env = True
    session.headers.update(BROWSER_HEADERS)
    try:
        resp = session.get(
            BLUESKY_SEARCH_URL,
            params={"q": query, "limit": limit, "sort": "latest"},
            timeout=timeout,
            proxies=_request_proxies(),
        )
    except requests.RequestException as exc:
        return 0, None, f"network error: {exc}"

    if resp.status_code != 200:
        preview = (resp.text or "")[:80].replace("\n", " ")
        return resp.status_code, None, f"HTTP {resp.status_code}: {preview}"

    try:
        return resp.status_code, resp.json(), ""
    except ValueError as exc:
        return resp.status_code, None, f"invalid JSON: {exc}"


def _rows_from_bluesky_payload(payload: dict, ticker: str, *, max_items: int) -> list[dict[str, str]]:
    posts = payload.get("posts", [])
    if not isinstance(posts, list):
        return []

    rows: list[dict[str, str]] = []
    collected = _utc_now()
    symbol = ticker.upper()

    for post in posts:
        if not isinstance(post, dict):
            continue
        record = post.get("record") if isinstance(post.get("record"), dict) else {}
        author = post.get("author") if isinstance(post.get("author"), dict) else {}
        text = _clean_text(record.get("text", ""))
        if not text:
            continue
        if symbol not in text.upper() and f"${symbol}" not in text.upper():
            continue

        handle = str(author.get("handle", "")).strip()
        uri = str(post.get("uri", "")).strip()
        rows.append(
            {
                "ticker": symbol,
                "title": text[:500],
                "summary": "",
                "published": str(record.get("createdAt", "")).strip(),
                "collected_at": collected,
                "source": "Bluesky",
                "url": _bluesky_url_from_uri(uri, handle),
                "social_sentiment": _sentiment_hint(text, ""),
                "_dedupe": _content_hash("bluesky", uri, text, ""),
            }
        )
        if max_items > 0 and len(rows) >= max_items:
            break
    return rows


def fetch_bluesky_social_posts(
    ticker: str,
    *,
    max_items: int = 30,
    timeout: int = 8,
) -> tuple[pd.DataFrame, str | None]:
    symbol = str(ticker).upper().strip()
    if not symbol:
        return pd.DataFrame(columns=SOCIAL_COLUMNS), "empty ticker"

    rows: list[dict[str, str]] = []
    errors: list[str] = []
    seen: set[str] = set()
    limit = max(max_items, 5) if max_items > 0 else 30

    for query in (f"${symbol}", symbol):
        status, payload, err = _fetch_bluesky_json(query, limit=limit, timeout=timeout)
        if payload is None:
            errors.append(f"{query}: {err or f'HTTP {status}'}")
            continue

        for row in _rows_from_bluesky_payload(payload, symbol, max_items=max_items):
            key = str(row.pop("_dedupe", ""))
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            rows.append(row)
            if max_items > 0 and len(rows) >= max_items:
                break
        if max_items > 0 and len(rows) >= max_items:
            break

    if rows:
        return pd.DataFrame(rows, columns=SOCIAL_COLUMNS), None

    err = "; ".join(errors[:3]) if errors else "no Bluesky posts found"
    return pd.DataFrame(columns=SOCIAL_COLUMNS), err


def _rows_from_reddit_payload(payload: dict, ticker: str, subreddit: str, *, max_items: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    children = payload.get("data", {}).get("children", [])
    if not isinstance(children, list):
        return rows

    collected = _utc_now()
    for child in children:
        data = child.get("data", {}) if isinstance(child, dict) else {}
        if not isinstance(data, dict):
            continue
        title = _clean_text(data.get("title", ""))
        text = _clean_text(data.get("selftext", ""))
        if not title and not text:
            continue
        if ticker.upper() not in f"{title} {text}".upper() and f"${ticker.upper()}" not in f"{title} {text}".upper():
            continue
        post_id = str(data.get("id", ""))
        rows.append(
            {
                "ticker": ticker.upper(),
                "title": title[:500],
                "summary": text[:500],
                "published": _published_from_utc(data.get("created_utc")),
                "collected_at": collected,
                "source": f"Reddit r/{subreddit}",
                "url": _reddit_permalink(str(data.get("permalink", ""))),
                "social_sentiment": _sentiment_hint(title, text),
                "_dedupe": _content_hash("reddit", post_id, title, text),
            }
        )
        if max_items > 0 and len(rows) >= max_items:
            break
    return rows


def fetch_reddit_social_posts(
    ticker: str,
    *,
    max_items: int = 30,
    timeout: int = 6,
    per_subreddit_limit: int = 10,
    max_subreddits: int | None = None,
) -> tuple[pd.DataFrame, str | None]:
    symbol = str(ticker).upper().strip()
    if not symbol:
        return pd.DataFrame(columns=SOCIAL_COLUMNS), "empty ticker"

    rows: list[dict[str, str]] = []
    errors: list[str] = []
    seen: set[str] = set()

    subreddits = _subreddits()[: max_subreddits or _max_subreddits()]
    for subreddit in subreddits:
        url = _reddit_search_url(subreddit, symbol, limit=per_subreddit_limit)
        status, text, content_type = _fetch_url(url, timeout=timeout)
        if status != 200:
            errors.append(f"r/{subreddit}: HTTP {status or 'N/A'}")
            continue
        if "json" not in content_type.lower() and not text.strip().startswith("{"):
            errors.append(f"r/{subreddit}: non-JSON response")
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append(f"r/{subreddit}: invalid JSON ({exc})")
            continue
        for row in _rows_from_reddit_payload(payload, symbol, subreddit, max_items=max_items):
            key = str(row.pop("_dedupe", ""))
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            rows.append(row)
            if max_items > 0 and len(rows) >= max_items:
                break
        if max_items > 0 and len(rows) >= max_items:
            break

    if rows:
        return pd.DataFrame(rows, columns=SOCIAL_COLUMNS), None
    err = "; ".join(errors[:4]) if errors else "no Reddit posts found"
    return pd.DataFrame(columns=SOCIAL_COLUMNS), err


def _sample_social_posts(ticker: str, *, max_items: int) -> pd.DataFrame:
    from src.news_filters import utc_today

    symbol = str(ticker).upper().strip()
    today = utc_today()
    collected = _utc_now()
    source_name = f"{_social_source().title()} sample"
    templates = [
        (f"${symbol} showing up in retail watchlists after recent price action.", "Bullish", 1, source_name),
        (f"Traders discussing ${symbol} volume and possible catalyst timing.", "", 2, source_name),
    ]
    rows: list[dict[str, str]] = []
    for title, sent, offset, source in templates:
        published_dt = datetime.combine(
            today - timedelta(days=offset),
            datetime.min.time(),
            tzinfo=timezone.utc,
        ).replace(hour=13, minute=0, second=0)
        rows.append(
            {
                "ticker": symbol,
                "title": title,
                "summary": "",
                "published": published_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "collected_at": collected,
                "source": source,
                "url": "",
                "social_sentiment": sent,
            }
        )
        if max_items > 0 and len(rows) >= max_items:
            break
    return pd.DataFrame(rows, columns=SOCIAL_COLUMNS)


def fetch_social_posts_with_error(
    ticker: str,
    *,
    max_items: int = 30,
    timeout: int = 6,
    max_subreddits: int | None = None,
) -> tuple[pd.DataFrame, str | None]:
    """Return social posts for a ticker without calling Stocktwits."""
    source = _social_source()
    if source == "bluesky":
        df, err = fetch_bluesky_social_posts(ticker, max_items=max_items, timeout=timeout)
    elif source == "reddit":
        df, err = fetch_reddit_social_posts(
            ticker,
            max_items=max_items,
            timeout=timeout,
            max_subreddits=max_subreddits,
        )
    else:
        return pd.DataFrame(columns=SOCIAL_COLUMNS), f"unsupported SOCIAL_SOURCE={source}"

    if not df.empty:
        return df, None
    if _allow_sample():
        sample = _sample_social_posts(ticker, max_items=max_items)
        if not sample.empty:
            return sample, None
    return df, err


def fetch_social_posts(ticker: str, *, max_items: int = 30, timeout: int = 6) -> pd.DataFrame:
    df, _err = fetch_social_posts_with_error(ticker, max_items=max_items, timeout=timeout)
    return df
