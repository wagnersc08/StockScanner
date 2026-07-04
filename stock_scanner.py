# -*- coding: utf-8 -*-
"""
Created on Sat Jul  4 15:28:07 2026

@author: wag08
"""

import os, json 
import pandas as pd 
import streamlit as st
from twelvedata import TDClient

API_KEY = 'd489129836fc49bd85c6e0234aadb14a' 
td=TDClient(apikey=API_KEY)

DEFAULT = [
    "ABEV3", "BBAS3", "BBSE3", "BOVA11", "CMIG4", "CMIN3",
    "DIVO11", "ISAE4", "LAVV3", "PETR4", "POMO4", "SAPR11",
    "SMAL11", "SMTO3", "VALE3",
    "VOO", "SCHD", "SPDW", "QQQ", "TLT", "CIBR",
    "BRK.B", "JNJ", "CVX", "UBER", "NKE", "DLR"
]
FILE='tickers.json'

def load():
    if os.path.exists(FILE):
        with open(FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    return DEFAULT

def save(lst): json.dump(lst,open(FILE,'w'),indent=2)

def sma(s,n): return s.rolling(n).mean()

def rsi(s, p=14):
    d = s.diff()

    g = d.clip(lower=0).rolling(p).mean()
    l = (-d.clip(upper=0)).rolling(p).mean().replace(0, 1e-9)

    rs = g / l

    return 100 - 100 / (1 + rs)


def get(symbol):

    ts = td.time_series(
        symbol=symbol,
        interval="1day",
        outputsize=250
    )

    df = ts.as_pandas()

    if df is None or df.empty:
        return None

    df = df.iloc[::-1].astype(float)

    return df


def analyze(t):

    try:

        df = get(t)

        if df is None:
            return None

        for n in [9, 21, 50, 200]:
            df[f"SMA{n}"] = sma(df["close"], n)

        df["RSI"] = rsi(df["close"])
        df["VOL20"] = df["volume"].rolling(20).mean()

        x = df.iloc[-1]

        score = 50

        if x["close"] > x["SMA21"]:
            score += 10

        if x["close"] > x["SMA50"]:
            score += 10

        if x["close"] > x["SMA200"]:
            score += 15

        if x["RSI"] < 30:
            score += 15

        elif 40 <= x["RSI"] <= 60:
            score += 10

        elif x["RSI"] > 70:
            score -= 15

        if x["volume"] > x["VOL20"]:
            score += 10

        score = max(0, min(100, score))

        if score >= 85:
            signal = "🟢 Compra Forte"
        elif score >= 70:
            signal = "🟢 Compra"
        elif score >= 55:
            signal = "🟡 Neutro"
        elif score >= 40:
            signal = "🟠 Atenção"
        else:
            signal = "🔴 Venda"

        return {
            "Ticker": t,
            "Preço": round(x["close"], 2),
            "RSI": round(x["RSI"], 1),
            "SMA9": round(x["SMA9"], 2),
            "SMA21": round(x["SMA21"], 2),
            "SMA50": round(x["SMA50"], 2),
            "SMA200": round(x["SMA200"], 2),
            "Volume": int(x["volume"]),
            "Vol.Médio20": int(x["VOL20"]),
            "Score": score,
            "Sinal": signal
        }

    except Exception as e:

        return {
            "Ticker": t,
            "Erro": str(e)
        }


st.set_page_config(layout="wide")

st.title("Scanner de Ativos - Twelve Data")

tickers = load()

txt = st.sidebar.text_area(
    "Tickers (1 por linha)",
    "\n".join(tickers),
    height=350
)

if st.sidebar.button("Salvar lista"):

    tickers = [
        i.strip().upper()
        for i in txt.splitlines()
        if i.strip()
    ]

    save(tickers)

    st.sidebar.success("Lista salva")


if st.button("Executar análise"):

    tickers = [
        i.strip().upper()
        for i in txt.splitlines()
        if i.strip()
    ]

    rows = []

    bar = st.progress(0)

    for i, t in enumerate(tickers):

        r = analyze(t)

        if r:
            rows.append(r)

        bar.progress((i + 1) / len(tickers))

    df = pd.DataFrame(rows)

    if "Score" in df.columns:
        df = df.sort_values("Score", ascending=False)

    st.dataframe(df, use_container_width=True)

    if "Ticker" in df.columns and "Score" in df.columns:

        sel = st.selectbox("Detalhes", df["Ticker"])

        if sel:

            st.write(
                df[df["Ticker"] == sel].T
            )