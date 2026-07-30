# Demo Recording Script

## 1. Opening

Hello Professor, this is my financial news sentiment analysis dashboard. The goal is to collect live stock screener data, related news, public newswire/RSS feeds, TradingView numeric screener data, Stocktwits social activity, sentiment, message volume, and alert signals in one Python dashboard.

## 2. Finviz Screener

Here on the left side, I can control the Finviz news date range, sector, minimum news count, and sorting method. The dashboard uses Finviz Elite data to load active stock tickers and news. The top metrics show how many tickers and news items are currently included.

I also added a TradingView numeric screener collector as a second market-data source. It can pull price, change percent, volume, market cap, pre-market, and post-market fields from TradingView's scanner endpoint and export the rows for comparison.

## 3. Ranked Tickers

In the Ranked tickers tab, I can compare tickers by live screener fields, news count, sentiment rank, and message density. This is the ranking part of the project. I can also export the table as a CSV file.

## 4. News Viewer

In the News viewer tab, I can inspect the actual news articles used for scoring. Each row includes the ticker, title, source, time, URL, and sentiment result. Besides Finviz, I added public RSS sources such as GlobeNewswire, PR Newswire, SEC, FDA, and custom RSS feeds. This helps me check whether the ranking is based on real news instead of only price movement.

## 5. Social / Stocktwits

In the Social tab, I added Stocktwits rolling window analysis. The Stocktwits chart range can be changed between 1D, 1W, 1M, 3M, 6M, YTD, 1Y, 5Y, and All. The ticker dropdown uses the same live ticker list as the Finviz chart selector.

## 6. Stocktwits Chart

This chart combines price, stock volume, message volume, and sentiment. The green line is the stock price. The bars are stock volume. The blue line is message volume. The purple line is sentiment. These values come from Stocktwits chart data when available.

## 7. Realtime Refresh

The dashboard refreshes every 60 seconds. I also connected a Stocktwits WebSocket quote stream, so after the program starts, the app can check for newer quote data every minute. The historical Stocktwits bars before the program starts still depend on the interval Stocktwits returns, so they may be 5-minute, 10-minute, or 30-minute bars.

## 8. Data Freshness

The Data freshness section shows the latest chart time, the WebSocket check time, the latest live quote time, and the latest social signal time. I added this because realtime data can be different from historical chart data, especially outside market hours.

## 9. Alerts

The Alerts section has three types of alerts. Realtime alerts check price movement after the app starts listening. Chart-window alerts check recent price movement and volume spikes inside the selected chart window. Social latest alerts check whether Stocktwits message volume or sentiment is very high or very bearish.

## 10. Correlation

The correlation table compares price changes with stock volume, message volume, and sentiment. This is a quick signal check, not trading advice, but it helps show whether social activity and price movement are moving together.

## 11. Closing

Overall, this project connects live Finviz data, TradingView numeric screener data, public RSS/newswire feeds, Stocktwits chart/social data, sentiment scoring, ranking, realtime quote checks, alerts, and export functions. Some bigger items, like broker trading, Redis/Kafka, licensed Dow Jones or Benzinga feeds, and options/futures modules, are listed as future extensions because they require more infrastructure, paid access, or trading permissions.
