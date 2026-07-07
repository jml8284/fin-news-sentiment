# IST 495 项目知识包 · fin-news-sentiment

**Jinyang Liu** · jml8284@psu.edu · Summer 2026  
**路径:** `/Users/ljjjy/fin-news-sentiment`  
**Repo:** https://github.com/jml8284/fin-news-sentiment  
**最后更新:** Week 8 (June 2026)

> 本文档打包：项目结构、教授要求、Week 6–8 成果、术语解释、演示话术、常见问题、文件清单、命令。

---

## 1. 项目是做什么的（一句话）

用 **Python + Streamlit** 从 **Finviz Elite** 抓 20 只强势股，抓 **新闻 + 社交帖**，用 **VADER/FinBERT** 做情绪分析，在 **Dashboard** 里实时展示排名、新闻密度和 K 线。

---

## 2. 个人信息 & 交付物

| 项目 | 内容 |
|------|------|
| 每周必交 | **Activity Log** Word（`Sample Activity-Log_IST495.docx` 模板） |
| 单独一次 | **Mockup** 界面草图（Canvas，FeedFlash 参考，不是每周交） |
| 不必每周做 | Canvas 里 video generation 公告（给视频组 intern 的 tips） |
| Week 7 log | `~/Downloads/IST495_Week7_Activity_Log_Jinyang_Liu.docx` |
| Week 8 log | 待写 |

---

## 3. Finviz「神秘代码」= API Token

- 文件：项目根目录 `.env` → `FINVIZ_API_TOKEN=...`
- 来源：登录 elite.finviz.com → **Settings → API**
- **Stocktwits 不需要 token**（公开 API）
- 改 `.env` 后必须 **Cmd+S 保存**，再重启 Streamlit
- 401 错误 → 重新生成 token，保存，重启

---

## 4. 教授批准的 Pipeline（底层逻辑）

```
Finviz 20 股 screener
  → 每 ticker 抓新闻（Finviz / Google / Yahoo / SEC）
  → clean
  → VADER 或 FinBERT 情绪
  → ticker 排名 + message_density
  → merge → CSV
  → Dashboard 展示
```

**Dashboard 现在（Week 7+）：** Ranked 表 + News 主要来自 **Live Finviz 网站抓取**，不是旧 CSV 快照。

### 教授 screener 预设（Jun 10, 2026）

- `v=151`, filters: `sh_curvol_o100,sh_relvol_o0.75,ta_change_u`, sort: `-change`
- 代码：`PRESET_TECHNICAL_GAINERS` in `src/finviz_config.py`

---

## 5. Dashboard 四个 Tab

| Tab | 做什么 | 数据来源 |
|-----|--------|----------|
| **Live Finviz chart** | K 线 + SMA + 该 ticker Finviz 新闻标题 | Live API |
| **Ranked tickers** | 20 股表格：价格、news_count、密度、排名 | Live screener + live 新闻 |
| **News viewer** | 每条 Finviz 新闻 + VADER 情绪 | Live 抓取 |
| **Stocktwits** | 社交帖子（Week 8） | api.stocktwits.com |

**60 秒刷新：** 只刷新 screener + chart；Finviz 新闻缓存约 5 分钟。点 **Refresh now** 强制重抓。

---

## 6. 表格列含义（必背）

| 列 | 含义 |
|----|------|
| **screener_rank** | Finviz screener 原始排名（按 change 等） |
| **sentiment_rank** | 按 live 新闻 VADER 情绪排名 |
| **news_count** | 选定日期范围内 **Finviz** 新闻条数 |
| **message_density** | 新闻密度：**Sparse** (0–1) / **Moderate** (2–3) / **Dense** (4+) |
| **stocktwits_count** | 同日期范围内 Stocktwits 帖子数（Week 8） |
| **social_density** | Stocktwits 密度，规则同 message_density |
| **price / change_pct / volume** | Live Finviz screener |

### 日期范围（Sidebar）

- Last 7 days / 30 days / 6 months / All on page / Custom
- **Week 6 功能**；改范围立刻重算 count，不必重新 scrape Finviz

---

## 7. VADER vs FinBERT

| | VADER | FinBERT |
|---|--------|---------|
| 是什么 | 词典+规则，快 | 深度学习金融模型 `ProsusAI/finbert` |
| 是否自己训练 | 否，现成库 | 否，下载现成模型 |
| Dashboard Live | **用 VADER**（快） | 不用（太慢） |
| 评估报告 | baseline | 升级对比 |
| 报告文件 | `data/processed/sentiment_eval_report.csv` + `.md` |
| PhraseBank 准确率 | ~57% | ~76% |

**跟教授说：** integrated and evaluated FinBERT, not trained.

---

## 8. evaluate_sentiment 测试是干什么的

- 用 **标准金融句子数据集**（PhraseBank、combined）对比 VADER 和 FinBERT 谁更准
- **不是**测 Dashboard，**不是**测 Finviz 抓取
- 跑命令：`python -m src.evaluate_sentiment --models vader,finbert`
- 会同时更新 CSV 和 MD 说明文件

---

## 9. Week 6 / 7 / 8 分工（你的口径）

### Week 6

- Live K 线、SMA 可选、60s 刷新
- 日期范围筛选 news_count / density
- screener_rank vs sentiment_rank
- 去掉 avg_sentiment 等重复列（教授反馈）
- Activity log 已完成

### Week 7

- **Live Dashboard**：Finviz screener + quote 新闻 live 抓取（非 CSV）
- **FinBERT** 集成 + `sentiment_eval_report`
- 修复 fragment 重复抓取导致 loading 卡死
- Live 用 VADER 打分

### Week 8

- **Stocktwits** API + Tab + stocktwits_count / social_density
- 本机 Stocktwits 常为 **0**（网络返回 HTML 非 JSON，不是缺 token）
- 黄色警告 = 部分 ticker Stocktwits 空；蓝色 = 整体说明网络问题

---

## 10. 教授 18 条 Roadmap（你做到哪了）

| # | 内容 | 你的进度 |
|---|------|----------|
| 2 | Finviz 新闻 | ✅ Live |
| 5 | Stocktwits 社交 | ✅ 代码完成，live 受网络限 |
| 6 | AI ranking | ✅ VADER + FinBERT eval |
| 7 | Numeric screener | ✅ price/volume/change |
| 其他 | Redis/Mongo/期权/券商等 | ❌ 后期 |

---

## 11. 常用命令

```bash
cd ~/fin-news-sentiment
source .venv/bin/activate

# 打开 Dashboard（演示用这个）
streamlit run src/dashboard.py

# 更新 pipeline CSV（可选）
python -m src.run_pipeline

# FinBERT 评估报告
python -m src.evaluate_sentiment --models vader,finbert

# 测试
python -m pytest tests/ -v

# 测 Stocktwits 网络
curl -s "https://api.stocktwits.com/api/2/streams/symbol/AAPL.json" | head -c 200
# 若看到 HTML 不是 JSON → 网络被挡
```

---

## 12. 关键文件地图

```
src/
  dashboard.py              # Streamlit 主界面
  finviz_config.py          # token + screener 预设
  collect_stocks.py         # 20 股 screener export
  collect_news.py           # Finviz 新闻 HTML 解析
  collect_stocktwits.py     # Week 8 Stocktwits API
  live_finviz_metrics.py    # Live Finviz 新闻+打分
  live_stocktwits_metrics.py# Week 8 社交指标
  sentiment_engines.py      # VADER + FinBERT
  evaluate_sentiment.py     # 模型对比 → CSV+MD
  finviz_charts.py          # K 线 quote_export
  ticker_ranking.py         # density_bucket 规则
  news_filters.py           # 日期解析、过滤

data/processed/
  sentiment_eval_report.csv # FinBERT vs VADER 数字
  sentiment_eval_report.md  # 同上，人类可读说明
  sentiment_engine.txt      # vader 或 finbert

reports/weekly_updates/     # 每周 update + activity log
```

---

## 13. 常见问题 FAQ

| 问题 | 答案 |
|------|------|
| Loading 一小时 | 旧 bug：60s 刷新重复抓新闻；已修。FinBERT live 也极慢，Dashboard 应用 VADER |
| Finviz 401 | 换 token，保存 .env，重启 |
| Stocktwits 全 0 | 网络挡 API，不需 token；代码和测试仍算 Week 8 完成 |
| 黄色 Stocktwits 警告 | 部分 ticker 没帖子，可忽略 |
| Mockup 每周交吗 | **不**，Canvas 单独作业 |
| message_density 啥意思 | 新闻多不多：Sparse/Moderate/Dense |
| 和 Stocktwits 区别 | message=Finviz 新闻；social=Stocktwits 帖 |

---

## 14. 给教授演示 — 简单英文（可复制）

**Opening:**  
"In Week 7 I built a live Finviz dashboard and added FinBERT evaluation. In Week 8 I added Stocktwits. Finviz works on my machine; Stocktwits is blocked by my network."

**Features (one line each):**

- Live screener: 20 stocks from Finviz Elite in real time.
- news_count: Finviz articles in the date range I pick.
- message_density: Sparse, Moderate, or Dense by article count.
- sentiment_rank: tickers ranked by VADER on live news.
- Live chart: candlesticks and SMA from Finviz.
- FinBERT report: 76% vs 57% on PhraseBank — file in data/processed.
- Stocktwits tab: social feed integrated; zero here is network, not missing code.

**Demo order:** Live fetch → Ranked tickers → change date range → Chart → News viewer → Stocktwits tab → open sentiment_eval_report.md

---

## 15. Canvas 公告（和你关系）

- **Video generation 系列**：其他 intern 录视频技巧；你若不交视频，了解即可。
- **Batch AI calls**：一次 API 处理多篇文章的优化建议，和 FinBERT 慢的问题相关。

---

## 16. 还没做 / 可选

- [ ] Week 8 Activity Log docx
- [ ] Mockup 草图（若 Canvas 未交）
- [ ] GitHub push（需 PAT）
- [ ] Redis 缓存（Week 9+ 可选）

---

## 17. 外部链接

- Finviz API: https://elite.finviz.com/api_explanation
- FinBERT: https://huggingface.co/ProsusAI/finbert
- FeedFlash 参考: https://feedflash-production.up.railway.app/
- VADER: https://github.com/cjhutto/vaderSentiment

---

*保存此文件到 repo；换电脑或新对话时可发给 AI 作上下文。*
