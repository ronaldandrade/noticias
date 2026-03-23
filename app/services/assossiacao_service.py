"""
services/associacao_service.py

Algoritmo de associação notícia → ativo com sistema de pontuação.

Problemas do algoritmo anterior:
  - Primeira ocorrência ganhava, independente de relevância
  - Palavras genéricas como "bolsa" e "B3" capturavam tudo para ^BVSP
  - Sem distinção entre menção principal e menção de contexto

Nova abordagem:
  - Cada ativo recebe uma pontuação baseada em quantas e quais palavras aparecem
  - Ticker explícito (PETR4, VALE3) vale muito mais que palavras genéricas
  - O ativo com maior pontuação ganha — não o primeiro da lista
  - Se nenhum ativo atingir pontuação mínima, retorna None (sem associação forçada)
"""

import re
from typing import Optional

# ── Palavras-chave por ativo com PESO por relevância ─────────────────────────
# Formato: {"KEYWORD": peso}
# Peso 10 = ticker explícito (match quase certo)
# Peso  5 = nome próprio específico da empresa
# Peso  2 = termo do setor (pode aparecer em contextos variados)
# Peso  1 = termo genérico (só reforça, nunca decide sozinho)

KEYWORDS_PONDERADAS: dict[str, dict[str, int]] = {

    "PETR4.SA": {
        "PETR4":        10,
        "PETR3":        10,
        "PETROBRAS":     5,
        "PETROBRÁS":     5,
        "PRÉ-SAL":       3,
        "PRE-SAL":       3,
        "PETRÓLEO":      2,
        "PETROLEO":      2,
        "COMBUSTÍVEL":   1,
        "COMBUSTIVEL":   1,
        "REFINARIA":     2,
        "GASOLINA":      1,
        "DIESEL":        1,
    },

    "VALE3.SA": {
        "VALE3":        10,
        "VALE":          5,
        "MINÉRIO":       3,
        "MINERIO":       3,
        "MINÉRIO DE FERRO": 4,
        "PELOTA":        3,
        "FERROVIA":      2,
        "CARAJÁS":       4,
        "SAMARCO":       4,
    },

    "ITUB4.SA": {
        "ITUB4":        10,
        "ITUB3":        10,
        "ITAÚ":          5,
        "ITAU":          5,
        "ITAÚ UNIBANCO": 6,
        "BANCO ITAÚ":    6,
        "BRADESCO":      0,  # concorrente — peso 0 para não confundir
    },

    "BBDC4.SA": {
        "BBDC4":        10,
        "BBDC3":        10,
        "BRADESCO":      5,
        "BANCO BRADESCO": 6,
    },

    "MGLU3.SA": {
        "MGLU3":        10,
        "MAGAZINE LUIZA": 6,
        "MAGALU":        6,
        "MAGAZINELUIZA": 6,
    },

    "^BVSP": {
        "IBOVESPA":      5,
        "IBOV":          4,
        "BVSP":          4,
        "B3":            2,  
        "BOLSA DE VALORES": 2,
        "BOVESPA":       3,
    },

    "^GSPC": {
        "S&P 500":       5,
        "S&P500":        5,
        "WALL STREET":   3,
        "NYSE":          3,
        "BOLSA AMERICANA": 3,
        "BOLSA DE NOVA YORK": 4,
    },

    "^DJI": {
        "DOW JONES":     5,
        "DJIA":          5,
        "DOW":           2,
    },

    "^IXIC": {
        "NASDAQ":        5,
        "NASDAQ 100":    6,
    },

    "BRL=X": {
        "DÓLAR":         4,
        "DOLAR":         4,
        "BRL":           3,
        "CÂMBIO":        3,
        "CAMBIO":        3,
        "COTAÇÃO DO DÓLAR": 5,
        "DÓLAR HOJE":    5,
        "USD/BRL":       6,
        "REAL BRASILEIRO": 3,
    },

    "EURUSD=X": {
        "EURO":          3,
        "EUR/USD":       6,
        "EURUSD":        6,
    },

    "GC=F": {
        "OURO":          4,
        "GOLD":          4,
        "METAL PRECIOSO": 3,
        "XAU":           5,
    },

    "CL=F": {
        "PETRÓLEO WTI":  6,
        "WTI":           5,
        "CRUDE OIL":     5,
        "BARRIL":        3,
    },

    "BZ=F": {
        "BRENT":         5,
        "PETRÓLEO BRENT": 6,
    },

    "BTC-USD": {
        "BITCOIN":       5,
        "BTC":           4,
        "CRIPTOMOEDA":   3,
        "CRIPTO":        2,
        "SATOSHI":       4,
        "BLOCKCHAIN":    2,
    },

    "ETH-USD": {
        "ETHEREUM":      5,
        "ETH":           4,
        "ETHER":         4,
    },
}

# Pontuação mínima para associar — evita associações fracas
PONTUACAO_MINIMA = 4


def associar_ativo(
    titulo: str,
    conteudo: str,
    ativos: list,
    pontuacao_minima: int = PONTUACAO_MINIMA,
) -> Optional[int]:
    """
    Retorna o ativo_id do ativo mais relevante para a notícia,
    ou None se nenhum atingir a pontuação mínima.

    O título tem peso dobrado em relação ao conteúdo — uma menção
    no título é muito mais significativa do que no corpo da notícia.
    """
    texto_titulo  = titulo.upper()
    texto_conteudo = conteudo[:600].upper()  # limita para evitar matches espúrios

    ativo_map = {a.ticker: a.id for a in ativos}
    pontuacoes: dict[str, int] = {}

    for ticker, keywords in KEYWORDS_PONDERADAS.items():
        if ticker not in ativo_map:
            continue  # ativo não cadastrado no banco

        pontos = 0
        for keyword, peso in keywords.items():
            if peso == 0:
                continue
            # Título vale dobrado
            if keyword in texto_titulo:
                pontos += peso * 2
            elif keyword in texto_conteudo:
                pontos += peso

        if pontos > 0:
            pontuacoes[ticker] = pontos

    if not pontuacoes:
        return None

    # Ativo com maior pontuação
    melhor_ticker = max(pontuacoes, key=lambda t: pontuacoes[t])
    melhor_pontos = pontuacoes[melhor_ticker]

    if melhor_pontos < pontuacao_minima:
        return None  # sem associação forçada

    return ativo_map[melhor_ticker]


def diagnosticar_associacao(titulo: str, conteudo: str, ativos: list) -> dict:
    
    texto_titulo   = titulo.upper()
    texto_conteudo = conteudo[:600].upper()
    ativo_map      = {a.ticker: a for a in ativos}
    resultado      = {}

    for ticker, keywords in KEYWORDS_PONDERADAS.items():
        if ticker not in ativo_map:
            continue

        detalhes = []
        pontos   = 0
        for keyword, peso in keywords.items():
            if peso == 0:
                continue
            if keyword in texto_titulo:
                pontos += peso * 2
                detalhes.append(f"{keyword}(título,+{peso*2})")
            elif keyword in texto_conteudo:
                pontos += peso
                detalhes.append(f"{keyword}(conteúdo,+{peso})")

        if pontos > 0:
            resultado[ticker] = {"pontos": pontos, "matches": detalhes}

    resultado["_minimo_necessario"] = PONTUACAO_MINIMA
    resultado["_vencedor"] = (
        max((t for t in resultado if not t.startswith("_")),
            key=lambda t: resultado[t]["pontos"],
            default=None)
    )
    return resultado