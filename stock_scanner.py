# -*- coding: utf-8 -*-
"""
Created on Sat Jul  4 15:28:07 2026

@author: wag08
"""

import os
import pandas as pd
import requests
from fastapi import FastAPI, Request
from twelvedata import TDClient

# =========================
# ENV VARIABLES (Render)
# =========================
TOKEN = os.environ["TELEGRAM_TOKEN"]
API_KEY = os.environ["TWELVEDATA_API_KEY"]

td = TDClient(apikey=API_KEY)

app = FastAPI()

TICKERS = [
    "ABEV3","BBAS3","BBSE3","BOVA11","CMIG4","CMIN3",
    "DIVO11","ISAE4","LAVV3","PETR4","POMO4","SAPR11",
    "SMAL11","SMTO3","VALE3",
    "VOO","SCHD","SPDW","QQQ","TLT","CIBR",
    "BRK.B","JNJ","CVX","UBER","NKE","DLR"
]

# =========================
# INDICADORES (SEM pandas_ta)
# =========================
def sma(series, period):
    return series.rolling(period).mean()

def rsi(series, period=14):
    delta = series.diff()

    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()

    rs = gain / loss.replace(0, 1e-10)

    return 100 - (100 / (1 + rs))


# =========================
# DATA
# =========================
def get_data(symbol):
    try:
        ts = td.time_series(
            symbol=symbol,
            interval="1day",
            outputsize=120
        )

        df = ts.as_pandas()

        if df is None or df.empty:
            return None

        df = df.iloc[::-1]
        df = df.astype(float)

        return df

    except Exception as e:
        print(f"Erro ao buscar {symbol}: {e}")
        return None


# =========================
# SCORE SYSTEM
# =========================
def score(last):

    s = 50

    # RSI
    if last["RSI"] < 30:
        s += 20
    elif last["RSI"] > 70:
        s -= 20

    # Tendência
    if last["close"] > last["SMA20"]:
        s += 10

    if last["close"] > last["SMA50"]:
        s += 10

    return max(0, min(100, s))


def classify(s):
    if s >= 80:
        return "🟢 FORTE COMPRA"
    elif s >= 60:
        return "🟡 NEUTRO"
    elif s >= 40:
        return "🟠 ATENÇÃO"
    return "🔴 VENDA"


# =========================
# SCANNER
# =========================
def run_scan():

    results = []

    for t in TICKERS:

        df = get_data(t)
        if df is None:
            continue

        df["SMA20"] = sma(df["close"], 20)
        df["SMA50"] = sma(df["close"], 50)
        df["RSI"] = rsi(df["close"], 14)

        last = df.iloc[-1]

        # proteção contra NaN
        if pd.isna(last["RSI"]):
            continue

        sc = score(last)

        results.append({
            "ticker": t,
            "score": sc,
            "signal": classify(sc)
        })

    df = pd.DataFrame(results)
    df = df.sort_values("score", ascending=False)

    return df.head(5)


# =========================
# TELEGRAM WEBHOOK
# =========================
@app.post("/webhook")
async def telegram_webhook(req: Request):

    data = await req.json()
    print("📩 UPDATE RECEBIDO:", data)

    message = data.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")

    if not text:
        return {"ok": True}

    # =========================
    # COMANDO /scan
    # =========================
    if text == "/scan":

        df = run_scan()

        msg = "📊 TOP ATIVOS\n\n"

        for _, row in df.iterrows():
            msg += f"{row['ticker']} | {row['score']} | {row['signal']}\n"

        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

        r = requests.post(url, data={
            "chat_id": chat_id,
            "text": msg
        })

        print("Telegram response:", r.text)

    else:

        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={
                "chat_id": chat_id,
                "text": "Comando inválido. Use /scan"
            }
        )

    return {"ok": True}


# =========================
# HEALTH CHECK (Render)
# =========================
@app.get("/")
def home():
    return {"status": "bot running"}