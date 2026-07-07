# Conversation Memory — IST 495 fin-news-sentiment

Persistent context from Cursor chat sessions. **Jinyang Liu** · Summer 2026.  
Last synced: **Week 7 (June 19, 2026)**

---

## Student & course

| Field | Value |
|-------|-------|
| Name | Jinyang Liu |
| Email | jml8284@psu.edu |
| Course | IST 495 Summer 2026 Internship (remote) |
| Project | Financial News Sentiment Analysis Dashboard |
| Repo | https://github.com/jml8284/fin-news-sentiment |
| Local path | `/Users/ljjjy/fin-news-sentiment` |
| IDE | Cursor / VS Code on macOS |

---

## Professor-approved pipeline

1. **Finviz Elite export API** + `FINVIZ_API_TOKEN` (professor account) → **20 stocks** from **Technical screener**
2. Per-ticker news: Elite `stock?t=TICKER` + Google + Yahoo + **SEC**
3. Clean → VADER sentiment → ticker ranking → **merge** → Streamlit dashboard

### Professor screener (Canvas Jun 10, 2026)

- `v=151`
- Filters: `sh_curvol_o100,sh_relvol_o0.75,ta_change_u` (updated from old `sh_relvol_o10`)
- Sort: `-change`
- Columns: `c=0,1,2,6,67,65,66,83,80,30,84,31,85,25,24,63,64,71,72,141,137,136,135`
- Code: `PRESET_TECHNICAL_GAINERS` in `src/finviz_config.py`

### Finviz Elite auth

- Browser login: professor shared Elite account (never put password in code)
- API: `FINVIZ_API_TOKEN` in `.env` only (from Settings → API page)
- Token regenerated Jun 2026; never commit `.env`
- **`load_dotenv(..., override=True)`** in `finviz_config.py` so `.env` wins over stale shell env
- Dashboard sidebar shows **token prefix** (`2ebd…`) — compare with Finviz Settings → API
- **Critical:** After editing `.env` in VS Code, **Cmd+S** must save to disk; unsaved editor ≠ what Streamlit reads

### Data accuracy rules (Week 6)

- **`news_count`** = total Finviz Elite quote-page news (professor ground truth); **not** duplicated as `finviz_news_count` in UI
- **`rolling_news_count`** = Finviz articles in selected date window
- **`supplemental_news_count`** = filtered Google/Yahoo/SEC (roundups excluded)
- **`avg_sentiment`** = mean VADER compound on **Finviz news in rolling window** only; 0 in window → N/A
- **`message_density`** (low/medium/high) from **`rolling_news_count`**, not total `news_count`
- Google roundup titles ("12 Stocks Moving...") excluded via `src/news_filters.py`
- Finviz published format `Feb-24-26 10:40AM` parsed in `news_filters.parse_published`

Professor long-term roadmap (18 items): FinBERT, Stocktwits, Redis/Kafka, MongoDB, etc. — future work.

---

## Week-by-week progress

### Week 1
- GitHub repo, README, folder structure, `requirements.txt`
- Pipeline skeleton + demo path with `demo_mock_news.csv`

### Week 2
- `collect_stocks.py` — Finviz screener, `demo_mock_stocks.csv`
- Report: `reports/weekly_updates/week2_update.md`

### Week 3
- `collect_news.py --from-stocks` — Google, Yahoo, Finviz per ticker
- Report: `reports/weekly_updates/week3_update.md`

### Week 4 (May 25–31)
- `merge_data.py`, `run_pipeline.py`, upgraded `dashboard.py`
- `finviz_config.py`, Elite mode, `.env.example`
- Deliverable: Week 4 activity log docx

### Week 5 (June 1–7)
- Production default (no `--demo`)
- `evaluate_sentiment.py` — PhraseBank ~57% acc, combined ~54%
- SEC RSS, optional MongoDB, pie chart, `collected_at` field
- Deliverable: Week 5 activity log docx

### Week 6 (June 8–14) — completed deliverables
- **Debugging & testing** focus; production data only (no demo for professor)
- **Live Finviz K-line chart** via `quote_export` API (`src/finviz_charts.py`)
- Dashboard: 3 tabs — Live chart, Ranked tickers, News viewer
- **Live screener table** in dashboard (Finviz export API, not stale CSV)
- Screener preset updated to professor Jun 10 filters (`v=151`, `sh_relvol_o0.75`)
- Finviz news cap raised to **80** per ticker (was 8)
- Split **`screener_rank`** vs **`sentiment_rank`**
- Unit tests: **22 passing** (`tests/`)
- Verified pipeline run: ~1045 news, 20 tickers (Jun 11, 2026)

#### Professor feedback (Jun 12 meeting ~8:20–8:40 AM) + fixes
1. **SMA indicators** — user multiselect in sidebar (`SMA overlays`); default daily 5/20, intraday 5/10
2. **Real-time** — `st.fragment(run_every=60)` for chart only (removed full-page meta refresh); change % from live screener when available
3. **avg_sentiment** — labeled `Mean sentiment (date range)` with column tooltips
4. **Duplicate columns** — removed `rank`, `finviz_news_count` from table; kept `news_count` + `rolling_news_count`
5. **Rolling window** — default **last 7 days**; presets Last 7 / Last 30 / **Custom From–To**; affects `avg_sentiment` + `message_density` only

#### Week 6 ops lessons
- **401 Unauthorized** → regenerate token on Finviz, save `.env` with Cmd+S, restart Streamlit
- **Sentiment columns all None** → live screener tickers changed since last pipeline; run `python -m src.run_pipeline`
- Dashboard shows warning when `X/20` tickers lack sentiment data

#### Week 6 deliverables
- Activity log: `/Users/ljjjy/Downloads/IST495_Week6_Activity_Log_Jinyang_Liu.docx` (~27 hrs)
- Copy in repo: `reports/weekly_updates/week6_activity_log_IST495.docx`

### Week 7 (June 15–21) — in progress
- **FinBERT integration** — `src/sentiment_engines.py`; `--engine vader|finbert` on sentiment step
- **Model evaluation** — `evaluate_sentiment.py --models vader,finbert` → `sentiment_eval_report.csv`
- **Pipeline** — `python -m src.run_pipeline --finbert --evaluate`
- **Week 6 fix** — chart fragment re-fetches live screener so change % updates with 60s refresh
- **Tests** — 28 passing (`tests/test_sentiment_engines.py` added)
- Report: `reports/weekly_updates/week7_update.md`

---

## Key files

| File | Role |
|------|------|
| `src/finviz_config.py` | Elite URLs, screener preset, token, quote_export URL builder |
| `src/collect_stocks.py` | Elite export → 20 stocks |
| `src/collect_news.py` | Multi-source news; Finviz max 80, others max 8 |
| `src/news_filters.py` | Finviz-only counting, roundup exclusion, `in_date_range`, Finviz date parse |
| `src/finviz_charts.py` | Live candlestick + selectable SMA + volume from quote_export |
| `src/clean_data.py` | HTML strip, dedup |
| `src/sentiment_engines.py` | VADER + FinBERT scorers; `--engine` selection |
| `src/sentiment_analysis.py` | VADER per article (default); `--engine finbert` optional |
| `src/ticker_ranking.py` | Finviz-only news_count; rolling window for avg_sentiment/density; `--window-days` |
| `src/merge_data.py` | stocks + sentiment → final_dataset.csv |
| `src/run_pipeline.py` | One command; `--evaluate`, `--mongo`, `--finviz-max-items` |
| `src/evaluate_sentiment.py` | VADER + FinBERT benchmark eval |
| `src/store_mongo.py` | Optional MongoDB |
| `src/dashboard.py` | Streamlit: live chart + live screener table + news viewer |
| `tests/` | pytest unit tests |
| `.env` | `FINVIZ_API_TOKEN` (never commit) |

---

## Commands (production)

```bash
cd /Users/ljjjy/fin-news-sentiment
source .venv/bin/activate

# Update all CSV data (stocks, news, sentiment, rankings)
python -m src.run_pipeline

# Optional FinBERT scoring + compare models on benchmarks
python -m src.run_pipeline --finbert --evaluate

# Evaluate only
python -m src.evaluate_sentiment --models vader,finbert

# Open dashboard (SEPARATE step — pipeline does not auto-open)
streamlit run src/dashboard.py

# Run tests
python -m pytest tests/ -v

# Offline demo only (NOT for professor)
python -m src.run_pipeline --demo
```

---

## Dashboard behavior (current)

| Tab | Data source | Refresh |
|-----|-------------|---------|
| **Live Finviz chart** | `quote_export` API | `st.fragment` ~60s |
| **Ranked tickers** | Live screener + pipeline sentiment (rolling window) | Screener live; sentiment after pipeline |
| **News viewer** | All sources from `sentiment_results.csv` | After pipeline |

Default chart interval: **D** (Daily). SMA overlays user-selectable.

Sentiment window sidebar: **Last 7 days** (default) / Last 30 / Custom From–To (UTC calendar days).

Old sentiment bar chart and pie chart **removed** — professor wants Finviz-style price chart.

---

## Common issues resolved

| Issue | Resolution |
|-------|------------|
| SCAG showed 9 news but Finviz news-free | `news_count` now Finviz-only |
| All news_count = 8 | Was collection cap; Finviz max now 80 |
| Table price ≠ Finviz live | Ranked tab now uses live screener API |
| `rank` column confusing when sorted by change | Split into screener_rank vs sentiment_rank |
| ASTX vs AXTX | Different tickers (not a bug) |
| Pipeline done but no dashboard | Must run `streamlit run src/dashboard.py` separately |
| `No module named 'src'` | dashboard.py adds project root to sys.path |
| Stale table vs Stocktwits | Compare with Finviz, not Stocktwits; re-run pipeline |
| 401 Finviz API | Regenerate token; Cmd+S save `.env`; restart Streamlit |
| `.env` edited but 401 persists | Editor had new token but disk still had old — verify file on disk |
| All sentiment None in table | Live screener tickers ≠ pipeline CSV tickers — `python -m src.run_pipeline` |

---

## Pending / not done

1. **GitHub push** — needs Personal Access Token
2. **Mockup assignment** — front end + secondary layers sketch (FeedFlash reference)
3. **MongoDB** — optional, code exists
4. **Re-run pipeline** after screener changes so sentiment columns populate for current 20 tickers
5. **FinBERT, Stocktwits, Redis** — professor roadmap, future

---

## External links

- Finviz Elite API: https://elite.finviz.com/api_explanation
- Finviz screener: https://elite.finviz.com/screener
- SEC press releases RSS: https://www.sec.gov/news/pressreleases.rss
- Streamlit: https://docs.streamlit.io/
- VADER: https://github.com/cjhutto/vaderSentiment
- FeedFlash reference: https://feedflash-production.up.railway.app/

---

## How AI should help going forward

- Prefer **minimal diffs**; match existing English code style in `src/`
- Never commit `.env` or expose API tokens/passwords
- Production = Finviz Elite only; no `--demo` for professor demos
- Distinguish live API data (chart/screener) vs pipeline CSV (sentiment/news viewer)
- User speaks Chinese; code and course deliverables stay **English**
- Read this file + `reports/activity_log.md` + latest `week*_update.md` when context is low
- Week 6 activity log template: `~/Downloads/Sample Activity-Log_IST495 (3).docx`

---

*Update this file after each major week or milestone.*
