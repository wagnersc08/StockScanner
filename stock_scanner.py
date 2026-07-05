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

st.set_page_config(page_title="Scanner de Ativos", layout="wide")
st.title("📈 Scanner de Ativos")

# =====================================================
# LISTA PADRÃO
# =====================================================

DEFAULT = [
    "ABEV3.SA", "BBAS3.SA", "BBSE3.SA", "BOVA11.SA", "CMIG4.SA",
    "CMIN3.SA", "DIVO11.SA", "ISAE4.SA", "ITUB4.SA", "ITSA4.SA", "LAVV3.SA", "PETR4.SA",
    "POMO4.SA", "SAPR11.SA", "SMAL11.SA", "SMTO3.SA", "VALE3.SA",
    "WEGE3.SA", "VOO", "SCHD", "SPDW", "QQQ", "TLT", "CIBR", "BRK-B",
    "JNJ", "CVX", "UBER", "NKE", "DLR"
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
        json.dump(lista, f, indent=4, ensure_ascii=False)

# =====================================================
# INDICADORES
# =====================================================

def sma(series, periodo):
    return series.rolling(periodo).mean()


def rsi(series, periodo=14):
    delta = series.diff()
    ganho = delta.clip(lower=0).rolling(periodo).mean()
    perda = (-delta.clip(upper=0)).rolling(periodo).mean()
    rs = ganho / perda.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)


def add_indicators(df):
    df = df.copy()
    df["SMA9"] = sma(df["close"], 9)
    df["SMA21"] = sma(df["close"], 21)
    df["SMA50"] = sma(df["close"], 50)
    df["SMA200"] = sma(df["close"], 200)
    df["RSI"] = rsi(df["close"])
    df["VOL20"] = df["volume"].rolling(20).mean()
    return df

# =====================================================
# DOWNLOAD DOS DADOS
# =====================================================

@st.cache_data(ttl=900, show_spinner=False)
def get(symbol):
    try:
        df = yf.download(
            tickers=symbol, period="1y", interval="1d",
            auto_adjust=True, progress=False, threads=False
        )

        if df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.columns = [c.lower() for c in df.columns]

        colunas = ["open", "high", "low", "close", "volume"]
        for c in colunas:
            if c not in df.columns:
                df[c] = np.nan

        df = df[colunas].dropna(subset=["close"])
        df["volume"] = df["volume"].fillna(0).astype(float)

        return df

    except Exception as e:
        print(f"Erro em {symbol}: {e}")
        return None

# =====================================================
# REGRAS DE SCORE
#
# Score orientado a "barateza" (mean-reversion / contrarian), não a
# tendência de alta. Cada regra recebe o df completo e devolve
# (pontos, motivo) ou None se não houver dado suficiente para avaliar.
#
# Ordem de prioridade (do peso maior pro menor):
#   1) Divergência de RSI     -> ±40
#   2) RSI simples             -> ±30
#   3) Desconto vs. SMA200     -> ±20
#   4) Variações de médias     -> ±5 (curto e longo prazo)
# =====================================================

def regra_sma_curto(df):
    ultimo = df.iloc[-1]
    if pd.isna(ultimo.SMA9) or pd.isna(ultimo.SMA21):
        return None
    if ultimo.SMA9 < ultimo.SMA21:
        return 5, "SMA9 < SMA21 (leve desconto de curto prazo)"
    return -5, "SMA9 > SMA21 (sem desconto de curto prazo)"


def regra_sma_longo(df):
    ultimo = df.iloc[-1]
    if pd.isna(ultimo.SMA50) or pd.isna(ultimo.SMA200):
        return None
    if ultimo.SMA50 < ultimo.SMA200:
        return 5, "SMA50 < SMA200 (papel fora de favor, possível barganha)"
    return -5, "SMA50 > SMA200 (sem desconto de médio prazo)"


def regra_preco_sma200(df):
    ultimo = df.iloc[-1]
    if pd.isna(ultimo.close) or pd.isna(ultimo.SMA200):
        return None
    if ultimo.close < ultimo.SMA200:
        return 20, "Preço abaixo da SMA200 (negociando com desconto)"
    return -20, "Preço acima da SMA200 (sem desconto, mais caro)"


def regra_rsi(df):
    ultimo = df.iloc[-1]
    if pd.isna(ultimo.RSI):
        return None
    if ultimo.RSI < 30:
        return 30, "RSI em sobrevenda (<30)"
    if ultimo.RSI > 70:
        return -30, "RSI em sobrecompra (>70)"
    return None


def encontrar_pivos(series, ordem=5):
    """
    Identifica fundos e topos locais: um ponto é pivô quando é o menor (ou
    maior) valor dentro de uma janela de 'ordem' dias para cada lado dele.
    """
    minimos, maximos = [], []
    n = len(series)

    for i in range(ordem, n - ordem):
        janela = series.iloc[i - ordem: i + ordem + 1]
        if series.iloc[i] == janela.min():
            minimos.append(i)
        if series.iloc[i] == janela.max():
            maximos.append(i)

    return minimos, maximos


def regra_divergencia_rsi(df, ordem=5, lookback=90):
    """
    Compara os dois últimos pivôs de preço (dentro da janela de 'lookback'
    dias) com o RSI no mesmo ponto:

    - Divergência de alta: preço faz fundo mais baixo, RSI faz fundo mais
      alto -> pressão vendedora enfraquecendo, possível reversão para cima.
    - Divergência de baixa: preço faz topo mais alto, RSI faz topo mais
      baixo -> força compradora enfraquecendo, possível reversão para baixo.
    """
    dados = df.iloc[-lookback:] if len(df) > lookback else df
    precos = dados["close"].reset_index(drop=True)
    rsis = dados["RSI"].reset_index(drop=True)

    minimos, maximos = encontrar_pivos(precos, ordem)

    if len(minimos) >= 2:
        i1, i2 = minimos[-2], minimos[-1]
        if precos[i2] < precos[i1] and rsis[i2] > rsis[i1]:
            return 40, "Divergência de alta no RSI (preço caiu, RSI subiu)"

    if len(maximos) >= 2:
        i1, i2 = maximos[-2], maximos[-1]
        if precos[i2] > precos[i1] and rsis[i2] < rsis[i1]:
            return -40, "Divergência de baixa no RSI (preço subiu, RSI caiu)"

    return None


# Ordem da lista não afeta o cálculo (todas as regras são somadas),
# mas segue a mesma ordem de prioridade dos pesos para facilitar leitura.
REGRAS = [regra_divergencia_rsi, regra_rsi, regra_preco_sma200, regra_sma_curto, regra_sma_longo]


def classificar(score):
    if score >= 85:
        return "🟢 Compra Forte"
    if score >= 70:
        return "🟢 Compra"
    if score >= 30:
        return "🟡 Neutro"
    return "🔴 Venda"


def analyze(ticker, df):
    if df is None or df.empty:
        return None

    ultimo = df.iloc[-1]
    score = 50
    motivos = []

    for regra in REGRAS:
        resultado = regra(df)
        if resultado:
            pontos, motivo = resultado
            score += pontos
            motivos.append(motivo)

    score = int(max(0, min(100, score)))
    r = lambda v: round(float(v), 2) if pd.notna(v) else None

    return {
        "Ticker": ticker,
        "Preço": r(ultimo.close),
        "RSI": r(ultimo.RSI),
        "SMA9": r(ultimo.SMA9),
        "SMA21": r(ultimo.SMA21),
        "SMA50": r(ultimo.SMA50),
        "SMA200": r(ultimo.SMA200),
        "Score": score,
        "Sinal": classificar(score),
        "Motivos": "; ".join(motivos) if motivos else "Sem sinais relevantes"
    }

# =====================================================
# INTERFACE - SIDEBAR
# =====================================================

st.sidebar.title("⚙️ Configurações")

tickers = load()
txt = st.sidebar.text_area("Tickers (um por linha)", "\n".join(tickers), height=420)

col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("💾 Salvar"):
        save([i.strip().upper() for i in txt.splitlines() if i.strip()])
        st.success("Lista salva!")
with col2:
    executar = st.button("▶ Executar")

# =====================================================
# EXECUÇÃO
# =====================================================

if executar:
    tickers = [i.strip().upper() for i in txt.splitlines() if i.strip()]

    resultados = []
    dados = {}  # guarda os df já processados, evita baixar/recalcular de novo no gráfico

    progresso = st.progress(0)
    status = st.empty()

    with st.spinner("Consultando Yahoo Finance..."):
        total = len(tickers)

        for i, ticker in enumerate(tickers):
            status.write(f"Baixando {ticker}...")

            df = get(ticker)

            if df is not None:
                df = add_indicators(df)
                dados[ticker] = df

                resultado = analyze(ticker, df)
                if resultado is not None:
                    resultados.append(resultado)

            progresso.progress((i + 1) / total)

    status.success("Concluído!")

    if not resultados:
        st.error("Nenhum ativo retornou dados.")
        st.stop()

    resultado = pd.DataFrame(resultados).sort_values("Score", ascending=False).reset_index(drop=True)

    # =====================================================
    # MÉTRICAS GERAIS
    # =====================================================

    metricas_gerais = [
        ("Ativos", len(resultado)),
        ("Compra Forte", (resultado["Score"] >= 85).sum()),
        ("Compra", ((resultado["Score"] >= 70) & (resultado["Score"] < 85)).sum()),
        ("Venda", (resultado["Score"] < 30).sum()),
    ]

    for col, (label, valor) in zip(st.columns(4), metricas_gerais):
        col.metric(label, valor)

    st.divider()

    # =====================================================
    # FILTRO E TABELA
    # =====================================================

    score_min = st.slider("Score mínimo", 0, 100, 0)
    resultado = resultado[resultado["Score"] >= score_min]

    st.subheader("Resultado")
    st.dataframe(resultado, use_container_width=True, hide_index=True)

    st.divider()

    # =====================================================
    # DETALHES DO ATIVO
    # =====================================================

    ativo = st.selectbox("Selecionar ativo", resultado["Ticker"])
    detalhe = resultado[resultado["Ticker"] == ativo].iloc[0]

    metricas_detalhe = [
        ("Preço", detalhe["Preço"]), ("RSI", detalhe["RSI"]), ("Score", detalhe["Score"]),
        ("SMA9", detalhe["SMA9"]), ("SMA21", detalhe["SMA21"]), ("SMA50", detalhe["SMA50"]),
    ]

    for linha_inicio in (0, 3):
        for col, (label, valor) in zip(st.columns(3), metricas_detalhe[linha_inicio:linha_inicio + 3]):
            col.metric(label, valor)

    st.metric("SMA200", detalhe["SMA200"])
    st.success(detalhe["Sinal"])
    st.info(detalhe["Motivos"])

    # =====================================================
    # GRÁFICO (reaproveita o df já calculado, sem baixar de novo)
    # =====================================================

    hist = dados.get(ativo)

    if hist is not None:
        st.subheader("Histórico")
        st.line_chart(hist[["close", "SMA21", "SMA50", "SMA200"]])