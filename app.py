# app.py
from flask import Flask, request, send_file, jsonify
import os, io, datetime, requests
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import mplfinance as mpf
import matplotlib.pyplot as plt
from telegram import Bot

# Config via env vars
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
FINNHUB_KEY = os.environ.get("FINNHUB_KEY")

bot = Bot(token=TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
app = Flask(__name__)

def fetch_ohlc_yf(ticker="GC=F", period="60d", interval="1h"):
    df = yf.download(tickers=ticker, period=period, interval=interval, progress=False, auto_adjust=False)
    df.dropna(inplace=True)
    return df

def calc_indicators(df):
    df['EMA20'] = ta.ema(df['Close'], length=20)
    df['EMA50'] = ta.ema(df['Close'], length=50)
    df['RSI14'] = ta.rsi(df['Close'], length=14)
    df['ATR14'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    return df

def find_swing_low_high(df, window=3):
    lows = df['Low']
    highs = df['High']
    swing_lows = lows[(lows.shift(window) > lows) & (lows.shift(-window) > lows)]
    swing_highs = highs[(highs.shift(window) < highs) & (highs.shift(-window) < highs)]
    return swing_lows, swing_highs

def generate_levels(df):
    last = df.iloc[-1]
    atr = last['ATR14'] if not np.isnan(last['ATR14']) else (df['Close'].pct_change().std() * last['Close'])
    ema20 = last['EMA20']; ema50 = last['EMA50']
    swing_lows, swing_highs = find_swing_low_high(df, window=3)
    last_swing_low = swing_lows.index.max() if not swing_lows.empty else None
    last_swing_high = swing_highs.index.max() if not swing_highs.empty else None
    if last_swing_low is not None:
        swing_low_price = df.loc[last_swing_low]['Low']
    else:
        swing_low_price = df['Low'].min()
    if last_swing_high is not None:
        swing_high_price = df.loc[last_swing_high]['High']
    else:
        swing_high_price = df['High'].max()

    bias = 'long' if ema20 > ema50 else 'short'

    if bias == 'long':
        sl = swing_low_price - 0.5*atr
        tp1 = last['Close'] + 1.0*atr
        tp2 = last['Close'] + 1.5*atr
        tp3 = swing_high_price if swing_high_price > last['Close'] else last['Close'] + 2.5*atr
        tp4 = last['Close'] + 3.5*atr
    else:
        sl = swing_high_price + 0.5*atr
        tp1 = last['Close'] - 1.0*atr
        tp2 = last['Close'] - 1.5*atr
        tp3 = swing_low_price if swing_low_price < last['Close'] else last['Close'] - 2.5*atr
        tp4 = last['Close'] - 3.5*atr

    return {
        'bias': bias,
        'entry': float(round(last['Close'], 3)),
        'SL': float(round(sl, 3)),
        'TP1': float(round(tp1, 3)),
        'TP2': float(round(tp2, 3)),
        'TP3': float(round(tp3, 3)),
        'TP4': float(round(tp4, 3)),
        'ATR': float(round(atr, 4)),
        'RSI': float(round(last['RSI14'], 2))
    }

def plot_and_annotate(df, levels, fname="xau_levels.png"):
    fig, ax = mpf.plot(df.tail(200), type='candle', style='charles',
                       mav=(20,50), volume=False, returnfig=True, figsize=(12,6))
    ax = fig.axes[0]
    entry = levels['entry']
    ax.axhline(entry, linestyle='--', linewidth=1, label='Entry')
    for k in ['TP1','TP2','TP3','TP4','SL']:
        price = levels[k]
        color = 'g' if k.startswith('TP') else 'r'
        ax.axhline(price, linestyle='-' if k=='SL' else '--', linewidth=1.2, label=f"{k} {price}")
        # place text to the right
        ax.text(df.index[-1], price, f" {k} {price}", va='center')
    buf = io.BytesIO()
    fig.savefig(buf, bbox_inches='tight', dpi=150)
    buf.seek(0)
    plt.close(fig)
    return buf

def fetch_recent_news_finnhub(symbols=["GOLD","XAUUSD"], minutes_window=120):
    if not FINNHUB_KEY:
        return []
    url = "https://finnhub.io/api/v1/news"
    try:
        r = requests.get(url, params={"category":"general","token":FINNHUB_KEY}, timeout=10)
        items = r.json()
    except Exception as e:
        return []
    recent = []
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=minutes_window)
    for it in items:
        ts = None
        if "datetime" in it and it.get("datetime"):
            try:
                ts = datetime.datetime.utcfromtimestamp(int(it.get("datetime")))
            except:
                ts = None
        if ts and ts >= cutoff:
            headline = it.get("headline","")
            for s in symbols:
                if s.lower() in headline.lower():
                    recent.append({"headline":headline,"datetime":ts.isoformat(),"source":it.get("source"),"url":it.get("url")})
                    break
    return recent

@app.route("/xau_mvp", methods=["GET"])
def xau_mvp():
    # Fetch data (yfinance GC=F fallback)
    try:
        df = fetch_ohlc_yf(ticker="GC=F", period="90d", interval="1h")
    except Exception as e:
        return jsonify({"error":"failed to fetch price data","detail":str(e)}), 500

    df = calc_indicators(df)
    lv = generate_levels(df)
    news = fetch_recent_news_finnhub(minutes_window=180)
    lv['news_count'] = len(news)

    img_buf = plot_and_annotate(df, lv)

    caption = f"XAUUSD ({datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')})\\nBias: {lv['bias']}\\nEntry: {lv['entry']}\\nSL: {lv['SL']}\\nTP1: {lv['TP1']}\\nTP2: {lv['TP2']}\\nTP3: {lv['TP3']}\\nTP4: {lv['TP4']}\\nATR: {lv['ATR']} RSI: {lv['RSI']}\\nNews hits (recent): {lv['news_count']}"
    # send to telegram if configured
    if bot:
        try:
            bot.send_photo(chat_id=os.environ.get("TELEGRAM_CHAT_ID"), photo=img_buf, caption=caption)
        except Exception as e:
            # continue and return result
            pass

    # Return image and JSON summary
    img_buf.seek(0)
    return send_file(img_buf, mimetype='image/png', as_attachment=False, download_name="xau_levels.png")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
