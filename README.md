
# XAU AI MVP - Finnhub + GC=F fallback + Telegram

This is a minimal MVP for a personalized XAUUSD (gold) trading assistant:
- Fetches hourly OHLC (yfinance `GC=F` fallback)
- Calculates EMA20/EMA50, RSI14, ATR14
- Generates SL and TP1..TP4 levels based on ATR + swings
- Fetches recent news from Finnhub (if FINNHUB_KEY provided) and counts relevant headlines
- Plots annotated chart and sends image to Telegram (if TELEGRAM_TOKEN & CHAT_ID set)

## Files
- app.py : Flask app with `/xau_mvp` endpoint
- requirements.txt : Python dependencies
- .env.example : example environment variables
- README.md : this file

## How to run (local)
1. Create virtualenv & install:
```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
2. Set environment variables (see `.env.example`), example:
```
export TELEGRAM_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"
export FINNHUB_KEY="your_finnhub_key"
```
3. Run:
```
python app.py
```
4. Open: `http://localhost:5000/xau_mvp` to get annotated image and (if configured) send to Telegram.

## Notes
- `GC=F` (Yahoo Finance) is used as fallback. For production use a broker or Polygon/IB for more accurate data.
- This MVP is a starting point — you should secure secrets, add logging, error handling, and production deployment (Docker, systemd, or cloud).
- Timeframe used: 1h. Adjust `fetch_ohlc_yf` interval/period to your preferred timeframe.

