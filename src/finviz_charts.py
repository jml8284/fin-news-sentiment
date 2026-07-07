"""
Live Finviz Elite intraday/daily bars via quote_export API + Plotly candlestick charts.
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
from plotly.subplots import make_subplots

from src.collect_stocks import DEFAULT_HEADERS
from src.finviz_config import build_quote_export_url, get_api_token
from src.news_filters import utc_today

PERIOD_OPTIONS: dict[str, str] = {
    "1M": "i1",
    "3M": "i3",
    "5M": "i5",
    "15M": "i15",
    "30M": "i30",
    "1H": "i60",
    "D": "d",
    "W": "w",
    "M": "m",
}

SMA_DAILY = (5, 10, 20, 30, 60, 90, 250)
SMA_INTRADAY = (5, 10, 30)
DEFAULT_SMA_DAILY = (5, 20)
DEFAULT_SMA_INTRADAY = (5, 10)


def available_sma_periods(period_label: str) -> tuple[int, ...]:
    if period_label in ("D", "W", "M"):
        return SMA_DAILY
    return SMA_INTRADAY


def default_sma_periods(period_label: str) -> tuple[int, ...]:
    if period_label in ("D", "W", "M"):
        return DEFAULT_SMA_DAILY
    return DEFAULT_SMA_INTRADAY
SMA_COLORS = {
    5: "#26a69a",
    10: "#ff9800",
    20: "#e91e63",
    30: "#2196f3",
    60: "#9c27b0",
    90: "#f44336",
    250: "#ffeb3b",
}

FINVIZ_GREEN = "#089981"
FINVIZ_RED = "#f23645"


def _find_column(df: pd.DataFrame, *names: str) -> str | None:
    lookup = {str(c).lower().strip(): c for c in df.columns}
    for name in names:
        key = name.lower()
        if key in lookup:
            return str(lookup[key])
    return None


def _parse_datetime(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", utc=True)
    if parsed.notna().any():
        return parsed
    return pd.to_datetime(series, errors="coerce", format="%m/%d/%Y %H:%M", utc=True)


def parse_quote_export_csv(content: bytes | str) -> pd.DataFrame:
    """Parse Finviz quote_export CSV into OHLCV bars."""
    if isinstance(content, bytes):
        if not content or len(content) < 10:
            raise ValueError("Empty quote export response from Finviz Elite")
        text = content.decode("utf-8", errors="replace")
    else:
        text = content

    text = text.strip()
    if not text:
        raise ValueError("Empty quote export response from Finviz Elite")

    df = pd.read_csv(io.StringIO(text))
    if df.empty:
        raise ValueError("Quote export CSV has no rows")

    time_col = _find_column(df, "date", "time", "datetime", "timestamp")
    open_col = _find_column(df, "open", "o")
    high_col = _find_column(df, "high", "h")
    low_col = _find_column(df, "low", "l")
    close_col = _find_column(df, "close", "c", "price")
    volume_col = _find_column(df, "volume", "vol", "v")

    if not all([time_col, open_col, high_col, low_col, close_col]):
        raise ValueError(f"Unexpected quote export columns: {list(df.columns)}")

    out = pd.DataFrame(
        {
            "datetime": _parse_datetime(df[time_col]),
            "open": pd.to_numeric(df[open_col], errors="coerce"),
            "high": pd.to_numeric(df[high_col], errors="coerce"),
            "low": pd.to_numeric(df[low_col], errors="coerce"),
            "close": pd.to_numeric(df[close_col], errors="coerce"),
            "volume": pd.to_numeric(df[volume_col], errors="coerce") if volume_col else 0.0,
        }
    )
    out = out.dropna(subset=["datetime", "open", "high", "low", "close"]).sort_values("datetime")
    out["volume"] = out["volume"].fillna(0.0)
    return out.reset_index(drop=True)


def filter_bars_by_date_window(
    bars: pd.DataFrame,
    *,
    window_start: date | None,
    window_end: date | None,
) -> pd.DataFrame:
    """Keep OHLCV bars whose UTC calendar date falls in window (inclusive)."""
    if bars.empty or (window_start is None and window_end is None):
        return bars.copy()

    start = window_start or date(2000, 1, 1)
    end = window_end or utc_today()
    if start > end:
        start, end = end, start

    dt = pd.to_datetime(bars["datetime"], utc=True)
    mask = (dt.dt.date >= start) & (dt.dt.date <= end)
    return bars.loc[mask].reset_index(drop=True)


def window_change_pct(bars: pd.DataFrame) -> float | None:
    """Percent change from first bar open to last bar close within a window."""
    if bars.empty:
        return None
    first_open = float(bars.iloc[0]["open"])
    last_close = float(bars.iloc[-1]["close"])
    if first_open == 0:
        return None
    return (last_close - first_open) / first_open * 100.0


def fetch_quote_bars(
    ticker: str,
    *,
    period: str = "i1",
    auth_token: str | None = None,
    timeout: int = 30,
) -> pd.DataFrame:
    """Download live OHLCV bars from Finviz Elite quote_export."""
    token = auth_token or get_api_token()
    url = build_quote_export_url(ticker, token, period=period)
    session = requests.Session()
    session.trust_env = False
    session.headers.update(DEFAULT_HEADERS)
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    return parse_quote_export_csv(resp.content)


def add_indicators(bars: pd.DataFrame, *, sma_periods: tuple[int, ...] = SMA_DAILY) -> pd.DataFrame:
    out = bars.copy()
    for period in sma_periods:
        out[f"sma_{period}"] = out["close"].rolling(window=period, min_periods=1).mean()
    typical = (out["high"] + out["low"] + out["close"]) / 3.0
    vol = out["volume"].replace(0, pd.NA)
    out["vwap"] = (typical * vol).cumsum() / vol.cumsum()
    out["vwap"] = out["vwap"].fillna(out["close"])
    return out


def build_finviz_style_chart(
    bars: pd.DataFrame,
    *,
    ticker: str,
    company: str = "",
    change_pct: float | None = None,
    period_label: str = "1M",
    sma_periods: tuple[int, ...] | None = None,
    window_label: str | None = None,
) -> go.Figure:
    """Dark-theme candlestick + volume + SMA/VWAP overlays (Finviz-like)."""
    if sma_periods is None:
        sma_periods = default_sma_periods(period_label)
    data = add_indicators(bars, sma_periods=sma_periods)
    if data.empty:
        raise ValueError("No bars to chart")

    title_parts = [f"{ticker.upper()}"]
    if company:
        title_parts.append(company)
    title = " · ".join(title_parts)
    if change_pct is not None and not pd.isna(change_pct):
        sign = "+" if change_pct >= 0 else ""
        title += f"  {sign}{change_pct:.2f}%"

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.75, 0.25],
    )

    use_category_x = len(data) <= 20
    if use_category_x:
        x_plot = pd.to_datetime(data["datetime"], utc=True).dt.strftime("%b %d")
    else:
        x_plot = data["datetime"]

    # Draw overlays first; candlesticks last so bodies stay visible (Finviz-style).
    for period in sma_periods:
        col_name = f"sma_{period}"
        fig.add_trace(
            go.Scatter(
                x=x_plot,
                y=data[col_name],
                mode="lines",
                name=f"SMA {period}",
                line=dict(width=1.0, color=SMA_COLORS.get(period, "#888888")),
                opacity=0.85,
            ),
            row=1,
            col=1,
        )

    if period_label not in ("D", "W", "M"):
        fig.add_trace(
            go.Scatter(
                x=x_plot,
                y=data["vwap"],
                mode="lines",
                name="VWAP",
                line=dict(width=1.2, color="#00bcd4"),
                opacity=0.9,
            ),
            row=1,
            col=1,
        )

    fig.add_trace(
        go.Candlestick(
            x=x_plot,
            open=data["open"],
            high=data["high"],
            low=data["low"],
            close=data["close"],
            name=ticker.upper(),
            increasing_line_color=FINVIZ_GREEN,
            increasing_fillcolor=FINVIZ_GREEN,
            decreasing_line_color=FINVIZ_RED,
            decreasing_fillcolor=FINVIZ_RED,
            line=dict(width=1),
        ),
        row=1,
        col=1,
    )

    colors = [
        FINVIZ_GREEN if row.close >= row.open else FINVIZ_RED
        for row in data.itertuples(index=False)
    ]
    fig.add_trace(
        go.Bar(
            x=x_plot,
            y=data["volume"],
            name="Volume",
            marker_color=colors,
            opacity=0.45,
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    fetched = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    subtitle = f"{period_label} · live @ {fetched}"
    if window_label:
        subtitle = f"{window_label} · {subtitle}"
    fig.update_layout(
        title=dict(text=f"{title} · {subtitle}", x=0.01, font=dict(size=15)),
        paper_bgcolor="#1a1a1a",
        plot_bgcolor="#1a1a1a",
        height=680,
        margin=dict(l=48, r=16, t=56, b=24),
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(26,26,26,0.7)",
            font=dict(size=10),
        ),
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=False, row=1, col=1, type="category" if use_category_x else "date")
    fig.update_xaxes(showgrid=False, row=2, col=1, type="category" if use_category_x else "date")
    fig.update_yaxes(showgrid=True, gridcolor="#333333", gridwidth=1, row=1, col=1)
    fig.update_yaxes(showgrid=False, row=2, col=1)

    return fig


def latest_price_info(bars: pd.DataFrame) -> dict[str, Any]:
    """Last bar price/volume; change vs previous bar close (Finviz-style)."""
    if bars.empty:
        return {}
    last = bars.iloc[-1]
    if len(bars) >= 2:
        ref_close = float(bars.iloc[-2]["close"])
    else:
        ref_close = float(last["open"])
    change_pct = ((float(last["close"]) - ref_close) / ref_close * 100.0) if ref_close else 0.0
    return {
        "price": float(last["close"]),
        "change_pct": float(change_pct),
        "volume": float(last["volume"]),
    }
