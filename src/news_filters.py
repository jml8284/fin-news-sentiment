"""
News quality filters aligned with Finviz Elite quote pages (professor ground truth).

Finviz "news-free" means zero rows on the stock?t= page — Google/Yahoo roundups
must not inflate news_count.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime

FINVIZ_PUBLISHED_RE = re.compile(
    r"^(?P<mon>[A-Za-z]{3})-(?P<day>\d{1,2})-(?P<yr>\d{2})\s+(?P<hr>\d{1,2}):(?P<min>\d{2})(?P<ampm>AM|PM)$",
    re.IGNORECASE,
)

DEFAULT_ROLLING_WINDOW_DAYS = 7


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def default_window_end() -> date:
    return utc_today()


def default_window_start(*, days: int = DEFAULT_ROLLING_WINDOW_DAYS) -> date:
    """Inclusive calendar window ending today (default: last 7 days)."""
    span = max(int(days), 1)
    return default_window_end() - timedelta(days=span - 1)


ROUNDUP_TITLE_RE = re.compile(
    r"("
    r"\d+\s+\w+\s+stocks?\s+moving"
    r"|which stocks are moving"
    r"|trending stocks today"
    r"|stocks to watch"
    r"|after the closing bell"
    r"|closing bell on"
    r")",
    re.IGNORECASE,
)


def is_finviz_source(source: object) -> bool:
    return "finviz" in str(source or "").lower()


def parse_published(value: object) -> datetime | None:
    if value is None or (isinstance(value, float) and str(value) == "nan"):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        pass
    finviz_match = FINVIZ_PUBLISHED_RE.match(text)
    if finviz_match:
        try:
            year = 2000 + int(finviz_match.group("yr"))
            hour = int(finviz_match.group("hr")) % 12
            if finviz_match.group("ampm").upper() == "PM":
                hour += 12
            dt = datetime(
                year,
                datetime.strptime(finviz_match.group("mon"), "%b").month,
                int(finviz_match.group("day")),
                hour,
                int(finviz_match.group("min")),
                tzinfo=timezone.utc,
            )
            return dt
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text[: len(fmt)], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    iso = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    return None


def is_recent(published: object, *, max_age_days: int) -> bool:
    if max_age_days <= 0:
        return True
    dt = parse_published(published)
    if dt is None:
        return False
    age = datetime.now(timezone.utc) - dt
    return age.days <= max_age_days


def in_date_range(
    published: object,
    *,
    start: date,
    end: date,
) -> bool:
    """True when published falls on start..end inclusive (UTC calendar days)."""
    dt = parse_published(published)
    if dt is None:
        return False
    if start > end:
        start, end = end, start
    start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end, time.max.replace(microsecond=0), tzinfo=timezone.utc)
    return start_dt <= dt <= end_dt


def mentions_ticker(title: str, summary: str, ticker: str, company: str = "") -> bool:
    blob = f"{title} {summary}".upper()
    symbol = ticker.upper().strip()
    if not symbol:
        return False
    if symbol in blob or f"({symbol})" in blob or f":{symbol}" in blob or f"NASDAQ:{symbol}" in blob:
        return True
    company_clean = company.strip()
    if company_clean and company_clean.upper() in blob:
        return True
    return False


def is_quality_supplemental(
    title: str,
    summary: str,
    ticker: str,
    *,
    company: str = "",
    published: object = "",
    max_age_days: int = 7,
) -> bool:
    """External (non-Finviz) article worth keeping for optional supplemental view."""
    if not title.strip():
        return False
    if ROUNDUP_TITLE_RE.search(title):
        return False
    if not mentions_ticker(title, summary, ticker, company):
        return False
    if not is_recent(published, max_age_days=max_age_days):
        return False
    return True
