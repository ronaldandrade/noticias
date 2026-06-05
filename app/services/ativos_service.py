"""
services/ativos_service.py
Fetches real-time prices, sentiment, news, and correlations for user assets.
"""
import logging
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf
import pandas as pd

from ..models import Noticia, Ativo, Correlacao
from .. import db

logger = logging.getLogger(__name__)

DEFAULT_ASSETS = [
    {"symbol": "BTC-USD",  "nome": "Bitcoin",   "categoria": "Cripto"},
    {"symbol": "^BVSP",    "nome": "Ibovespa",  "categoria": "Índice"},
    {"symbol": "^GSPC",    "nome": "S&P 500",   "categoria": "Índice"},
    {"symbol": "^DJI",     "nome": "Dow Jones", "categoria": "Índice"},
    {"symbol": "^IXIC",    "nome": "Nasdaq",    "categoria": "Índice"},
    {"symbol": "USDBRL=X", "nome": "Dólar",     "categoria": "Câmbio"},
    {"symbol": "BRLUSD=X", "nome": "Real",      "categoria": "Câmbio"},
    {"symbol": "GC=F",     "nome": "Ouro",      "categoria": "Commodity"},
    {"symbol": "CL=F",     "nome": "Petróleo",  "categoria": "Commodity"},
]

DEFAULT_SYMBOLS = {a["symbol"] for a in DEFAULT_ASSETS}

B3_ATIVOS = [
    {"symbol": "PETR4",  "nome": "Petrobras PN"},
    {"symbol": "VALE3",  "nome": "Vale ON"},
    {"symbol": "ITUB4",  "nome": "Itaú Unibanco PN"},
    {"symbol": "BBDC4",  "nome": "Bradesco PN"},
    {"symbol": "ABEV3",  "nome": "Ambev ON"},
    {"symbol": "WEGE3",  "nome": "WEG ON"},
    {"symbol": "BBAS3",  "nome": "Banco do Brasil ON"},
    {"symbol": "BPAC11", "nome": "BTG Pactual UNT"},
    {"symbol": "SUZB3",  "nome": "Suzano ON"},
    {"symbol": "RENT3",  "nome": "Localiza ON"},
    {"symbol": "LREN3",  "nome": "Lojas Renner ON"},
    {"symbol": "MGLU3",  "nome": "Magazine Luiza ON"},
    {"symbol": "RDOR3",  "nome": "Rede D'Or ON"},
    {"symbol": "HAPV3",  "nome": "Hapvida ON"},
    {"symbol": "GGBR4",  "nome": "Gerdau PN"},
    {"symbol": "CSNA3",  "nome": "CSN ON"},
    {"symbol": "USIM5",  "nome": "Usiminas PNA"},
    {"symbol": "CMIG4",  "nome": "Cemig PN"},
    {"symbol": "ELET3",  "nome": "Eletrobras ON"},
    {"symbol": "EQTL3",  "nome": "Equatorial ON"},
    {"symbol": "TAEE11", "nome": "Taesa UNT"},
    {"symbol": "ENGI11", "nome": "Energisa UNT"},
    {"symbol": "KLBN11", "nome": "Klabin UNT"},
    {"symbol": "JBSS3",  "nome": "JBS ON"},
    {"symbol": "BRFS3",  "nome": "BRF ON"},
    {"symbol": "HYPE3",  "nome": "Hypera ON"},
    {"symbol": "RADL3",  "nome": "Raia Drogasil ON"},
    {"symbol": "TOTS3",  "nome": "Totvs ON"},
    {"symbol": "PRIO3",  "nome": "PetroRio ON"},
    {"symbol": "CSAN3",  "nome": "Cosan ON"},
    {"symbol": "RAIL3",  "nome": "Rumo ON"},
    {"symbol": "CCRO3",  "nome": "CCR ON"},
    {"symbol": "FLRY3",  "nome": "Fleury ON"},
    {"symbol": "MULT3",  "nome": "Multiplan ON"},
    {"symbol": "EMBR3",  "nome": "Embraer ON"},
    {"symbol": "AZUL4",  "nome": "Azul PN"},
    {"symbol": "GOLL4",  "nome": "Gol PN"},
    {"symbol": "CYRE3",  "nome": "Cyrela ON"},
    {"symbol": "MRVE3",  "nome": "MRV ON"},
    {"symbol": "TIMS3",  "nome": "TIM ON"},
    {"symbol": "VIVT3",  "nome": "Vivo ON"},
    {"symbol": "NTCO3",  "nome": "Grupo Natura ON"},
    {"symbol": "VBBR3",  "nome": "Vibra Energia ON"},
    {"symbol": "COGN3",  "nome": "Cogna ON"},
    {"symbol": "YDUQ3",  "nome": "Yduqs ON"},
]


def _to_yf_symbol(symbol: str) -> str:
    """Convert a clean symbol to its yfinance ticker string."""
    if symbol in DEFAULT_SYMBOLS:
        return symbol
    if symbol.endswith(".SA"):
        return symbol
    return symbol + ".SA"


def _fetch_one(symbol: str) -> dict | None:
    """Fetch 30d OHLCV history for a single symbol from yfinance."""
    yf_sym = _to_yf_symbol(symbol)
    try:
        ticker = yf.Ticker(yf_sym)
        hist = ticker.history(period="30d", interval="1d")
    except Exception as exc:
        logger.warning("yfinance error for %s: %s", yf_sym, exc)
        return None

    if hist.empty:
        return None

    if isinstance(hist.columns, pd.MultiIndex):
        hist.columns = hist.columns.get_level_values(0)

    closes = hist["Close"].dropna()
    if len(closes) < 1:
        return None

    preco_atual   = float(closes.iloc[-1])
    preco_ant     = float(closes.iloc[-2]) if len(closes) > 1 else preco_atual
    variacao_pct  = ((preco_atual - preco_ant) / preco_ant * 100) if preco_ant else 0.0

    volume = 0
    if "Volume" in hist.columns:
        vol_ser = hist["Volume"].dropna()
        if not vol_ser.empty:
            volume = int(vol_ser.iloc[-1])

    last7   = closes.tail(7)
    last30  = closes

    return {
        "preco":           round(preco_atual, 4),
        "variacao":        round(variacao_pct, 2),
        "volume":          volume,
        "sparkline_7d":    [round(float(v), 4) for v in last7.tolist()],
        "sparkline_7d_labels": [str(d.date()) for d in last7.index.tolist()],
        "sparkline_30d":   [round(float(v), 4) for v in last30.tolist()],
        "sparkline_30d_labels": [str(d.date()) for d in last30.index.tolist()],
    }


def fetch_price_batch(symbols: list[str]) -> dict:
    """Fetch current price + sparkline for multiple symbols (parallel)."""
    results: dict = {}
    workers = min(len(symbols), 6)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_fetch_one, s): s for s in symbols}
        for future in as_completed(futures):
            sym = futures[future]
            try:
                results[sym] = future.result()
            except Exception as exc:
                logger.warning("fetch_one error for %s: %s", sym, exc)
                results[sym] = None
    return results


def fetch_ytd(symbol: str) -> dict | None:
    """Fetch YTD price history for detail modal."""
    yf_sym = _to_yf_symbol(symbol)
    try:
        ticker = yf.Ticker(yf_sym)
        hist = ticker.history(period="ytd", interval="1d")
    except Exception:
        return None

    if hist.empty:
        return None

    if isinstance(hist.columns, pd.MultiIndex):
        hist.columns = hist.columns.get_level_values(0)

    closes = hist["Close"].dropna()
    return {
        "labels": [str(d.date()) for d in closes.index.tolist()],
        "values": [round(float(v), 4) for v in closes.tolist()],
    }


def get_sentiment_for_symbol(symbol: str) -> dict | None:
    """Return sentiment scores and correlation for a tracked B3 asset."""
    ticker_sa = _to_yf_symbol(symbol)
    ativo = Ativo.query.filter(
        db.or_(Ativo.ticker == ticker_sa, Ativo.ticker == symbol)
    ).first()

    if not ativo:
        return None

    hoje   = date.today()
    semana = hoje - timedelta(days=7)
    mes    = hoje - timedelta(days=30)

    def _avg(rows):
        scores = [r[0] for r in rows]
        return round(sum(scores) / len(scores), 4) if scores else None

    rows_7d = (
        db.session.query(Noticia.score_sentimento)
        .filter(Noticia.ativo_id == ativo.id,
                Noticia.score_sentimento.isnot(None),
                Noticia.data_publicacao >= semana)
        .all()
    )
    rows_30d = (
        db.session.query(Noticia.score_sentimento)
        .filter(Noticia.ativo_id == ativo.id,
                Noticia.score_sentimento.isnot(None),
                Noticia.data_publicacao >= mes)
        .all()
    )

    corr = (
        Correlacao.query
        .filter_by(ativo_id=ativo.id)
        .order_by(Correlacao.data_fim.desc())
        .first()
    )

    return {
        "score_7d":    _avg(rows_7d),
        "score_30d":   _avg(rows_30d),
        "n_noticias":  len(rows_7d),
        "pearson":     round(corr.pearson, 3) if corr and corr.pearson is not None else None,
    }


def get_noticias_for_symbol(symbol: str, limit: int = 5) -> list[dict]:
    """Return recent news from DB for a B3 ticker."""
    ticker_sa = _to_yf_symbol(symbol)
    ativo = Ativo.query.filter(
        db.or_(Ativo.ticker == ticker_sa, Ativo.ticker == symbol)
    ).first()

    if not ativo:
        return []

    noticias = (
        Noticia.query
        .filter(Noticia.ativo_id == ativo.id)
        .order_by(Noticia.data_publicacao.desc())
        .limit(limit)
        .all()
    )

    def _classe(s):
        if s is None:  return "neutro"
        if s > 0.05:   return "positivo"
        if s < -0.05:  return "negativo"
        return "neutro"

    return [
        {
            "titulo": n.titulo,
            "score":  n.score_sentimento,
            "classe": _classe(n.score_sentimento),
            "url":    n.url,
            "data":   n.data_publicacao.strftime("%d/%m %H:%M"),
        }
        for n in noticias
    ]


def buscar_b3(query: str) -> list[dict]:
    """Search B3 assets by ticker or name (DB first, then curated list)."""
    q = query.upper().strip()
    results = []
    seen: set[str] = set()

    db_ativos = Ativo.query.filter(
        db.or_(
            Ativo.ticker.ilike(f"%{q}%"),
            Ativo.nome.ilike(f"%{query}%"),
        )
    ).limit(10).all()

    for a in db_ativos:
        clean = a.ticker.replace(".SA", "")
        if clean not in seen:
            results.append({"symbol": clean, "nome": a.nome})
            seen.add(clean)

    for a in B3_ATIVOS:
        if q in a["symbol"] or query.lower() in a["nome"].lower():
            if a["symbol"] not in seen:
                results.append({"symbol": a["symbol"], "nome": a["nome"]})
                seen.add(a["symbol"])

    return results[:15]
