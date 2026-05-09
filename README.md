
# Financial News Sentiment Analysis Dashboard

## Project Description

This project is for my IST 495 internship. The goal is to build a Python-based financial news sentiment analysis system. The system will collect financial news related to stock tickers, analyze sentiment, calculate message density, and display ranked tickers in a dashboard.

## Main Goals

- Collect financial news from online sources or RSS feeds.
- Clean and organize news data.
- Identify related stock tickers.
- Analyze sentiment for each news item.
- Calculate ticker-level sentiment scores and message density.
- Build a dashboard to display ranked stock tickers and recent news.

## Planned Project Structure

```text
fin-news-sentiment/
├── README.md
├── requirements.txt
├── data/
│   ├── raw/
│   └── processed/
├── src/
│   ├── collect_news.py
│   ├── clean_data.py
│   ├── sentiment_analysis.py
│   ├── ticker_ranking.py
│   └── dashboard.py
├── notebooks/
│   └── exploration.ipynb
└── reports/
    └── weekly_updates/
