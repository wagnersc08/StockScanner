# -*- coding: utf-8 -*-
"""
Created on Sat Jul  4 15:28:07 2026

@author: wag08
"""
import os
import json
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Scanner de Ativos",
    layout="wide"
)

st.title("📈 Scanner de Ativos")

# =====================================================
# LISTA PADRÃO
# =====================================================

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

# =====================================================
# TICKERS
# =====================================================

def load():

    if os.path.exists(FILE):

        with open(FILE, "r", encoding="utf-8") as f:

            return json.load(f)

    return DEFAULT


def save(lista):

    with open(FILE, "w", encoding="utf-8") as f:

        json.dump(
            lista,
            f,
            indent=4,
            ensure_ascii=False
        )

# =====================================================
# MÉDIAS
# =====================================================

def sma(series, periodo):

    return series.rolling(periodo).mean()

# =====================================================
# RSI
# =====================================================

def rsi(series, periodo=14):

    delta = series.diff()

    ganho = delta.clip(lower=0)

    perda = -delta.clip(upper=0)

    ganho = ganho.rolling(periodo).mean()

    perda = perda.rolling(periodo).mean()

    rs = ganho / perda.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    return rsi.fillna(50)

# =====================================================
# DOWNLOAD DOS DADOS
# =====================================================

@st.cache_data(ttl=900, show_spinner=False)
def get(symbol):

    try:

        df = yf.download(
            tickers=symbol,
            period="1y",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False
        )

        if df.empty:
            return None

        # Corrige MultiIndex (algumas versões do yfinance retornam assim)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Colunas em minúsculas
        df.columns = [c.lower() for c in df.columns]

        # Mantém somente colunas necessárias
        colunas = ["open", "high", "low", "close", "volume"]

        for c in colunas:

            if c not in df.columns:

                df[c] = np.nan

        df = df[colunas]

        # Remove linhas sem preço
        df = df.dropna(subset=["close"])

        # Volume pode vir vazio em alguns ETFs
        df["volume"] = (
            df["volume"]
            .fillna(0)
            .astype(float)
        )

        return df

    except Exception as e:

        print(f"Erro em {symbol}: {e}")

        return None
    
# =====================================================
# INDICADORES
# =====================================================

def add_indicators(df):

    df = df.copy()

    df["SMA9"] = sma(df["close"], 9)

    df["SMA21"] = sma(df["close"], 21)

    df["SMA50"] = sma(df["close"], 50)

    df["SMA200"] = sma(df["close"], 200)

    df["RSI"] = rsi(df["close"])

    df["VOL20"] = (
        df["volume"]
        .rolling(20)
        .mean()
    )

    return df

# =====================================================
# INTERFACE
# =====================================================

st.sidebar.title("⚙️ Configurações")

tickers = load()

txt = st.sidebar.text_area(
    "Tickers (um por linha)",
    "\n".join(tickers),
    height=420
)

col1, col2 = st.sidebar.columns(2)

with col1:

    if st.button("💾 Salvar"):

        nova_lista = [
            i.strip().upper()
            for i in txt.splitlines()
            if i.strip()
        ]

        save(nova_lista)

        st.success("Lista salva!")

with col2:

    executar = st.button("▶ Executar")


# =====================================================
# EXECUÇÃO
# =====================================================

if executar:

    tickers = [
        i.strip().upper()
        for i in txt.splitlines()
        if i.strip()
    ]

    resultados = []

    progresso = st.progress(0)

    status = st.empty()

    with st.spinner("Consultando Yahoo Finance..."):

        total = len(tickers)

        for i, ticker in enumerate(tickers):

            status.write(f"Baixando {ticker}...")

            df = get(ticker)

            if df is None:

                progresso.progress((i + 1) / total)

                continue

            df = add_indicators(df)

            resultado = analyze(ticker)

            if resultado is not None:

                resultados.append(resultado)

            progresso.progress((i + 1) / total)

    status.success("Concluído!")

    if len(resultados) == 0:

        st.error("Nenhum ativo retornou dados.")

        st.stop()

    resultado = pd.DataFrame(resultados)

    resultado = resultado.sort_values(
        "Score",
        ascending=False
    ).reset_index(drop=True)

    # =====================================================
    # MÉTRICAS
    # =====================================================

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Ativos",
        len(resultado)
    )

    c2.metric(
        "Compra Forte",
        (resultado["Score"] >= 85).sum()
    )

    c3.metric(
        "Compra",
        (
            (resultado["Score"] >= 70) &
            (resultado["Score"] < 85)
        ).sum()
    )

    c4.metric(
        "Venda",
        (resultado["Score"] < 40).sum()
    )

    st.divider()

    # =====================================================
    # FILTRO
    # =====================================================

    score_min = st.slider(
        "Score mínimo",
        0,
        100,
        0
    )

    resultado = resultado[
        resultado["Score"] >= score_min
    ]

    # =====================================================
    # TABELA
    # =====================================================

    st.subheader("Resultado")

    st.dataframe(
        resultado,
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # =====================================================
    # DETALHES
    # =====================================================

    ativo = st.selectbox(
        "Selecionar ativo",
        resultado["Ticker"]
    )

    detalhe = resultado[
        resultado["Ticker"] == ativo
    ].iloc[0]

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Preço",
        detalhe["Preço"]
    )

    c2.metric(
        "RSI",
        detalhe["RSI"]
    )

    c3.metric(
        "Score",
        detalhe["Score"]
    )

    c1.metric(
        "SMA9",
        detalhe["SMA9"]
    )

    c2.metric(
        "SMA21",
        detalhe["SMA21"]
    )

    c3.metric(
        "SMA50",
        detalhe["SMA50"]
    )

    st.metric(
        "SMA200",
        detalhe["SMA200"]
    )

    st.success(
        detalhe["Sinal"]
    )

    st.info(
        detalhe["Motivos"]
    )

    # =====================================================
    # GRÁFICO
    # =====================================================

    hist = get(ativo)

    if hist is not None:

        hist = add_indicators(hist)

        graf = hist[
            [
                "close",
                "SMA21",
                "SMA50",
                "SMA200"
            ]
        ]

        st.subheader("Histórico")

        st.line_chart(graf)