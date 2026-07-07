# Complete Project Memory Export — fin-news-sentiment

**Exported:** July 1, 2026  
**Student:** Jinyang Liu · jml8284@psu.edu · IST 495 Summer 2026  
**For:** New Cursor chats / professor email / personal backup

---

## Project location

| Item | Path / URL |
|------|------------|
| **Local project root** | `/Users/ljjjy/fin-news-sentiment` |
| **GitHub repo** | https://github.com/jml8284/fin-news-sentiment |
| **Virtual env** | `/Users/ljjjy/fin-news-sentiment/.venv` |
| **Secrets (.env)** | `/Users/ljjjy/fin-news-sentiment/.env` — **never commit** |
| **Knowledge pack (中文)** | `reports/IST495_knowledge_pack_Jinyang_Liu.md` |
| **Shorter memory** | `reports/conversation_memory.md` |
| **This full export** | `reports/conversation_memory_full_export.md` |

### Open / run

```bash
cd /Users/ljjjy/fin-news-sentiment
source .venv/bin/activate
streamlit run src/dashboard.py
```

In Cursor: **File → Open Folder →** `/Users/ljjjy/fin-news-sentiment`

---

## One-sentence project summary

Python + Streamlit dashboard: **Finviz Elite** live screener (20 tickers), news, K-line chart, VADER sentiment ranking; **Stocktwits** optional social tab; FinBERT for offline evaluation.

---

## Professor-approved pipeline

1. Finviz Elite export API + `FINVIZ_API_TOKEN` → 20 stocks (Technical screener)
2. Per-ticker news: Finviz quote page + Google + Yahoo + SEC
3. Clean → VADER (live) / FinBERT (pipeline eval) → ranking → merge → dashboard

**Screener preset** (`PRESET_TECHNICAL_GAINERS` in `src/finviz_config.py`):
- `v=151`, filters: `sh_curvol_o100,sh_relvol_o0.75,ta_change_u`, sort: `-change`

**Finviz auth:** token in `.env` only; after edit **Cmd+S** + restart Streamlit.

---

## Dashboard current state (July 2026)

### Four tabs

| Tab | Data | Notes |
|-----|------|-------|
| **Live Finviz chart** | `quote_export` API | Full K-line by default; optional rolling window |
| **Ranked tickers** | Live screener + live Finviz news metrics | Finviz only; no Stocktwits columns |
| **News viewer** | Live Finviz news + VADER | Filtered by Finviz news date range |
| **Stocktwits** | Optional social tab | Isolated from Finviz; fetch off by default |

### Sidebar sections (separate)

1. **Finviz filters** — News date range (7d / 30d / 6mo / All / Custom) → `news_count`, News viewer
2. **Live Finviz chart** — ticker, interval, SMA, **Enable K-line rolling window** (off by default)
3. **Stocktwits** — Enable fetch (off by default), own date range, Refresh Stocktwits

### Week 9 rolling window design

- **Finviz news range** always applies to ranked table + news viewer
- **K-line rolling window** is **manual optional toggle** — when off, full Finviz history
- When on: Chart quick range (7d / 30d / 6mo / All / Custom), window change %, bars-in-window
- 7 calendar days + daily interval ≈ **5 bars** (weekends) — **normal**, not a bug

### Auto-refresh

- `st.fragment(run_every=60)` for screener + chart
- Finviz news cached ~5 min
- Stocktwits cached ~15 min when enabled

---

## Week-by-week progress

| Week | Dates | Done |
|------|-------|------|
| 1–5 | May–Jun | Repo, pipeline, merge, evaluate, Mongo optional |
| 6 | Jun 8–14 | Live K-line, SMA, rolling news window, screener_rank vs sentiment_rank, professor feedback fixes |
| 7 | Jun 15–21 | Live Finviz dashboard, FinBERT eval, sentiment_engines, fragment refresh fix |
| 8 | Jun 22–28 | Stocktwits API + tab + metrics; rate limits; sample fallback |
| 9 | Jun 29–Jul 5 | K-line `filter_bars_by_date_window`, optional chart window; Finviz/Stocktwits split |

---

## Stocktwits — detailed problem (simulated + verified)

### Symptom (Dashboard)

- Blue banner: *"Showing sample posts (live API blocked or rate-limited)"*
- Total messages often **40** (20 tickers × 2 each)
- Changing date range (7d → 6mo) changes **label** but not **count**
- Finviz tabs remain fully live

### Root cause (external)

- Endpoint: `https://api.stocktwits.com/api/2/streams/symbol/{TICKER}.json`
- Returns **HTTP 403 Forbidden** on student's network
- `STOCKTWITS_ACCESS_TOKEN` in `.env` is **empty**
- Stocktwits developer registration reportedly closed / Partner API may be required
- Professor (Jun 30): *"You seem to be scraping stocktwits or too much. Slow down on your calls."*

### Mitigations already in code

| Setting | Default | Purpose |
|---------|---------|---------|
| `STOCKTWITS_MIN_INTERVAL_SEC` | 5 | Gap between HTTP calls |
| `STOCKTWITS_LIVE_TICKER_LIMIT` | 5 | Only 5 tickers try live API per refresh |
| `STOCKTWITS_WEB_FALLBACK` | 0 | Web scrape off (avoid more blocks) |
| `STOCKTWITS_ALLOW_SAMPLE` | 1 | Bundled demo when live fails |
| Fetch checkbox in UI | off | No calls until user enables |
| Sequential fetch | yes | No parallel 20-ticker blast |
| Circuit breaker | yes | After 2× 403/429 → sample for rest |

### Code behavior issue (why professor sees "success" but it's fake)

**Simulated 403 run (mock API returns 403 for every ticker):**

```
Single ticker LHAI: rows=2, err=None, source=Stocktwits (sample)
8 tickers: total=16, errors=[], each ticker count=2
20 tickers → 40 messages, errors=[]
```

Flow in `fetch_stocktwits_messages_with_error()`:
1. API → 403
2. Web fallback → disabled
3. Sample fallback → enabled → returns data with **`error=None`**
4. Dashboard thinks fetch succeeded; only `source` field reveals sample

**Key files:**
- `src/collect_stocktwits.py` — API, web, sample
- `src/live_stocktwits_metrics.py` — sequential fetch, limits
- `scripts/verify_stocktwits.py` — local diagnostic
- `data/samples/stocktwits_messages.json` — AAPL/TSLA/NVDA etc.; screener tickers get **2 generic template posts**

### Verify locally

```bash
python scripts/verify_stocktwits.py AAPL          # see 403 + sample
STOCKTWITS_ALLOW_SAMPLE=0 python scripts/verify_stocktwits.py AAPL  # see real error
python -m pytest tests/test_stocktwits.py -v
```

---

## VADER vs FinBERT

| | VADER | FinBERT |
|---|--------|---------|
| Dashboard live | ✅ fast | ❌ too slow |
| Pipeline / eval | baseline | upgrade |
| PhraseBank accuracy | ~57% | ~76% |
| Tell professor | "integrated and evaluated FinBERT, not trained" |

---

## Key source files

| File | Role |
|------|------|
| `src/dashboard.py` | Streamlit UI (Finviz + Stocktwits split) |
| `src/finviz_charts.py` | K-line, SMA, `filter_bars_by_date_window`, `window_change_pct` |
| `src/live_finviz_metrics.py` | Live Finviz news fetch + date filter + metrics |
| `src/collect_stocktwits.py` | Stocktwits API / web / sample |
| `src/live_stocktwits_metrics.py` | Stocktwits dashboard metrics |
| `src/finviz_config.py` | Elite URLs, screener preset, token |
| `src/sentiment_engines.py` | VADER + FinBERT |
| `src/evaluate_sentiment.py` | Model benchmark |
| `src/news_filters.py` | Date parsing, `in_date_range` |
| `tests/` | pytest (finviz, stocktwits, sentiment, etc.) |

---

## Course deliverables status

| Deliverable | Status |
|-------------|--------|
| Weekly Activity Log (.docx) | Week 6/7 done; Week 8/9 md in repo, docx may need export |
| Mockup (FeedFlash ref) | May still be pending |
| GitHub push | May need PAT |
| Redis cache | Optional Week 9+ |

**Week 9 docs in repo** (may need update to match optional K-line window + Finviz/ST split):
- `reports/weekly_updates/week9_update.md`
- `reports/weekly_updates/week9_activity_log_IST495.md`

---

## Professor communication (Jul 1, 2026)

- Professor asked student to use Claude/Cursor on 403
- Student explained: slowed calls, sample fallback, Finviz still live
- Core technical story: **403 is real; sample hides failure (`error=None`); 40 messages = demo data**

---

## Commands cheat sheet

```bash
cd /Users/ljjjy/fin-news-sentiment && source .venv/bin/activate

# Dashboard
streamlit run src/dashboard.py

# Pipeline (CSV sentiment for pipeline-based workflows)
python -m src.run_pipeline
python -m src.run_pipeline --finbert --evaluate

# Tests
python -m pytest tests/ -v
python -m pytest tests/test_stocktwits.py tests/test_finviz_charts.py -v

# Diagnostics
python scripts/verify_stocktwits.py AAPL
python scripts/verify_live_finviz.py
```

---

## Rules for future AI sessions

- User speaks **Chinese**; code and course docs in **English**
- Never commit `.env` or expose Finviz token / passwords
- Minimal diffs; match existing `src/` style
- Finviz = primary live demo; Stocktwits = optional, explain sample if 403
- Do not merge Stocktwits back into Finviz tabs unless user asks
- K-line rolling window stays **optional manual toggle**
- Read this file + `IST495_knowledge_pack_Jinyang_Liu.md` when context is low

---

## Pending / optional next work (user declined for now)

- Sync K-line window with Finviz news range
- CSV export ranked table
- Calendar-day bar count hint on chart
- Update week9_update.md to match current UI
- Week 9 activity log docx export

---

*End of full memory export. Update after major milestones.*
