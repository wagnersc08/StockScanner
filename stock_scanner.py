# -*- coding: utf-8 -*-
"""
Created on Sat Jul  4 15:28:07 2026

@author: wag08
"""
import os
import json
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(layout="wide")

DEFAULT = [
    "ABEV3.SA",
    "BBAS3.SA",
    "BBSE3.SA",
    "BOVA11.SA",
    "CMIG4.SA",
    "CMIN3.SA",
    "DIVO11.SA",
    "ISAE4.SA",
    "LAVV3.SA",
    "PETR4.SA",
    "POMO4.SA",
    "SAPR11.SA",
    "SMAL11.SA",
    "SMTO3.SA",
    "VALE3.SA",
    "VOO",
    "SCHD",
    "SPDW",
    "QQQ",
    "TLT",
    "CIBR",
    "BRK-B",
    "JNJ",
    "CVX",
    "UBER",
    "NKE",
    "DLR"
]

FILE = "tickers.json"


def load():

    if os.path.exists(FILE):

        with open(FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    return DEFAULT


def save(lst):

    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(lst, f, indent=4)


def sma(series, period):

    return series.rolling(period).mean()


def rsi(series, period=14):

    delta = series.diff()

    gain = delta.where(delta > 0, 0).rolling(period).mean()

    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()

    rs = gain / loss.replace(0, 1e-9)

    return 100 - (100 / (1 + rs))

@st.cache_data(ttl=3600)
def get(symbol):

    try:

        df = yf.download(
            symbol,
            period="1y",
            interval="1d",
            progress=False,
            auto_adjust=True
        )

        if df.empty:
            return None

        df = df.rename(columns=str.lower)

        return df

    except Exception as e:

        print(symbol, e)

        return None
    
def analyze(ticker):

    df = get(ticker)

    if df is None:
        return None

    # Médias móveis
    df["SMA9"] = sma(df["close"], 9)
    df["SMA21"] = sma(df["close"], 21)
    df["SMA50"] = sma(df["close"], 50)
    df["SMA200"] = sma(df["close"], 200)

    # RSI
    df["RSI"] = rsi(df["close"])

    # Volume médio
    df["VOL20"] = df["volume"].rolling(20).mean()

    last = df.iloc[-1]

    score = 50

    motivos = []

    # ---------- Tendência ----------

    if last["close"] > last["SMA9"]:
        score += 5
        motivos.append("Acima da SMA9")

    if last["close"] > last["SMA21"]:
        score += 10
        motivos.append("Acima da SMA21")

    if last["close"] > last["SMA50"]:
        score += 10
        motivos.append("Acima da SMA50")

    if last["close"] > last["SMA200"]:
        score += 15
        motivos.append("Acima da SMA200")

    # ---------- Cruzamento ----------

    if last["SMA21"] > last["SMA50"]:
        score += 5
        motivos.append("SMA21 > SMA50")

    if last["SMA50"] > last["SMA200"]:
        score += 10
        motivos.append("SMA50 > SMA200")

    # ---------- RSI ----------

    if last["RSI"] < 30:
        score += 15
        motivos.append("RSI Sobrevendido")

    elif 40 <= last["RSI"] <= 60:
        score += 10
        motivos.append("RSI Saudável")

    elif last["RSI"] > 70:
        score -= 15
        motivos.append("RSI Sobrecomprado")

    # ---------- Volume ----------

    if last["volume"] > last["VOL20"]:
        score += 10
        motivos.append("Volume acima da média")

    score = max(0, min(100, score))

    # ---------- Classificação ----------

    if score >= 85:
        sinal = "🟢 Compra Forte"

    elif score >= 70:
        sinal = "🟢 Compra"

    elif score >= 55:
        sinal = "🟡 Neutro"

    elif score >= 40:
        sinal = "🟠 Atenção"

    else:
        sinal = "🔴 Venda"

    return {

        "Ticker": ticker,

        "Preço": round(last["close"], 2),

        "RSI": round(last["RSI"], 1),

        "SMA9": round(last["SMA9"], 2),

        "SMA21": round(last["SMA21"], 2),

        "SMA50": round(last["SMA50"], 2),

        "SMA200": round(last["SMA200"], 2),

        "Volume": int(last["volume"]),

        "Vol. Médio": int(last["VOL20"]),

        "Score": score,

        "Sinal": sinal,

        "Motivos": ", ".join(motivos)
    }

# ======================================================
# INTERFACE STREAMLIT
# ======================================================

st.title("📈 Scanner de Ativos")

st.write(
    "Análise baseada em Médias Móveis, RSI e Volume utilizando Yahoo Finance."
)

tickers = load()

txt = st.sidebar.text_area(
    "Tickers (1 por linha)",
    "\n".join(tickers),
    height=400
)

col1, col2 = st.sidebar.columns(2)

with col1:

    if st.button("Executar análise"):

        tickers = [
            t.strip().upper()
            for t in txt.splitlines()
            if t.strip()
        ]

        resultados = []

        progresso = st.progress(0)

        status = st.empty()

        for i, ticker in enumerate(tickers):

            status.write(f"Analisando {ticker}...")

            resultado = analyze(ticker)

            if resultado is not None:
                resultados.append(resultado)

            progresso.progress((i + 1) / len(tickers))

        status.success("Análise concluída!")

        df = pd.DataFrame(resultados)

        if len(df) > 0:

            df = df.sort_values(
                by="Score",
                ascending=False
            )

            st.subheader("Resultado")

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

            st.subheader("Detalhes")

            ativo = st.selectbox(
                "Selecione um ativo",
                df["Ticker"]
            )

            detalhe = df[df["Ticker"] == ativo]

            c1, c2 = st.columns(2)

            with c1:

                st.metric(
                    "Preço",
                    detalhe["Preço"].values[0]
                )

                st.metric(
                    "RSI",
                    detalhe["RSI"].values[0]
                )

                st.metric(
                    "Score",
                    detalhe["Score"].values[0]
                )

                st.metric(
                    "Sinal",
                    detalhe["Sinal"].values[0]
                )

            with c2:

                st.metric(
                    "SMA9",
                    detalhe["SMA9"].values[0]
                )

                st.metric(
                    "SMA21",
                    detalhe["SMA21"].values[0]
                )

                st.metric(
                    "SMA50",
                    detalhe["SMA50"].values[0]
                )

                st.metric(
                    "SMA200",
                    detalhe["SMA200"].values[0]
                )

            st.subheader("Justificativa")

            st.info(
                detalhe["Motivos"].values[0]
            )

            st.subheader("Histórico")

            hist = get(ativo)

            if hist is not None:

                graf = hist[["close"]].copy()

                graf["SMA21"] = sma(
                    graf["close"],
                    21
                )

                graf["SMA50"] = sma(
                    graf["close"],
                    50
                )

                graf["SMA200"] = sma(
                    graf["close"],
                    200
                )

                st.line_chart(graf)

        else:

            st.error("Nenhum ativo retornou dados.")

with col2:

    if st.button("Salvar lista"):

        lista = [
            t.strip().upper()
            for t in txt.splitlines()
            if t.strip()
        ]

        save(lista)

        st.success("Lista salva com sucesso!")