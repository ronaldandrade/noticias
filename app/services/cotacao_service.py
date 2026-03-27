"""
services/cotacao_service.py

Responsabilidades:
  1. Buscar cotações históricas via yfinance e salvar na tabela Cotacao
  2. Calcular correlação sentimento × retorno e salvar na tabela Correlacao
"""
import logging
from datetime import date, timedelta

import yfinance as yf
import pandas as pd
from scipy import stats
from curl_cffi.requests import Session

from ..models import Ativo, Cotacao, Correlacao, Noticia
from .. import db


logger = logging.getLogger(__name__)


# ── 1. Buscar e salvar cotações ───────────────────────────────────────────────

def buscar_cotacoes(ativo: Ativo, dias: int = 90) -> list[Cotacao]:

    data_inicio = date.today() - timedelta(days=dias)

    try:
        df = yf.download(
            ativo.ticker,
            start=data_inicio.isoformat(),
            progress=False,
            auto_adjust=True,   # ajusta splits e dividendos automaticamente
        )
    except Exception as exc:
        logger.error("yfinance falhou para %s: %s", ativo.ticker, exc)
        return []

    if df.empty:
        logger.warning("Nenhum dado retornado para %s", ativo.ticker)
        return []

    # yfinance pode retornar MultiIndex quando baixa um único ticker
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.rename(columns={
        "Close": "close",
        "Open":  "open",
        "Volume": "volume",
    })
    df["variacao_pct"] = df["close"].pct_change() * 100
    df = df.dropna(subset=["close"])

    novas: list[Cotacao] = []
    for data_idx, row in df.iterrows():
        data_cot = data_idx.date() if hasattr(data_idx, "date") else data_idx

        existe = Cotacao.query.filter_by(
            ativo_id=ativo.id, data=data_cot
        ).first()
        if existe:
            continue

        cotacao = Cotacao(
            ativo_id=ativo.id,
            data=data_cot,
            preco_fechamento=float(row["close"]),
            preco_abertura=float(row["open"]) if "open" in row else None,
            variacao_pct=float(row["variacao_pct"]) if pd.notna(row["variacao_pct"]) else None,
            volume=int(row["volume"]) if "volume" in row and pd.notna(row["volume"]) else None,
        )
        novas.append(cotacao)

    if novas:
        try:
            db.session.bulk_save_objects(novas)
            db.session.commit()
            logger.info("%s: %d cotações salvas.", ativo.ticker, len(novas))
        except Exception as exc:
            db.session.rollback()
            logger.error("Erro ao salvar cotações de %s: %s", ativo.ticker, exc)
            raise

    return novas

def buscar_cotacoes_todos_ativos(dias=90):
    ativos = Ativo.query.all()
    # Criamos a sessão que "engana" o firewall do Yahoo
    session = Session(impersonate="chrome")
    
    for ativo in ativos:
        try:
            # Passamos a sessão explicitamente aqui
            df = yf.download(ativo.ticker, period=f"{dias}d", session=session)
            if not df.empty:
                ativos = Ativo.query.all()
                for ativo in ativos:
                    buscar_cotacoes(ativo, dias=dias)
        except Exception as e:
            logger.error(f"Erro em {ativo.ticker}: {e}")

# ── 2. Calcular correlação sentimento × retorno ───────────────────────────────

def calcular_correlacao(
    ativo: Ativo,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> Correlacao | None:
    """
    Alinha notícias (por data_publicacao) com cotações (por data) do ativo,
    calcula Pearson e Spearman entre score_sentimento e variacao_pct,
    salva o resultado na tabela Correlacao e retorna o objeto.

    """
    data_fim    = data_fim    or date.today()
    data_inicio = data_inicio or (data_fim - timedelta(days=90))

    # Carrega notícias do período com score preenchido
    noticias_q = (
        Noticia.query
        .filter(
            Noticia.ativo_id == ativo.id,
            Noticia.score_sentimento.isnot(None),
            Noticia.data_publicacao >= data_inicio,
            Noticia.data_publicacao <= data_fim,
        )
        .all()
    )

    if not noticias_q:
        logger.warning("Nenhuma notícia com score para %s no período.", ativo.ticker)
        return None

    # Agrega score médio por data
    df_noticias = pd.DataFrame([
        {
            "data": n.data_publicacao.date(),
            "score": n.score_sentimento,
        }
        for n in noticias_q
    ])
    df_noticias = df_noticias.groupby("data")["score"].mean().reset_index()

    # Carrega cotações do período
    cotacoes_q = (
        Cotacao.query
        .filter(
            Cotacao.ativo_id == ativo.id,
            Cotacao.data >= data_inicio,
            Cotacao.data <= data_fim,
            Cotacao.variacao_pct.isnot(None),
        )
        .all()
    )

    if not cotacoes_q:
        logger.warning("Nenhuma cotação disponível para %s no período.", ativo.ticker)
        return None

    df_cotacoes = pd.DataFrame([
        {"data": c.data, "variacao_pct": c.variacao_pct}
        for c in cotacoes_q
    ])

    # Merge por data (inner join — só datas com ambos os dados)
    df = pd.merge(df_noticias, df_cotacoes, on="data", how="inner")

    if len(df) < 5:
        logger.warning(
            "Poucos pontos de interseção (%d) para calcular correlação de %s.",
            len(df), ativo.ticker,
        )
        return None

    pearson_r,  _ = stats.pearsonr(df["score"], df["variacao_pct"])
    spearman_r, _ = stats.spearmanr(df["score"], df["variacao_pct"])

    correlacao = Correlacao(
        ativo_id=ativo.id,
        data_inicio=data_inicio,
        data_fim=data_fim,
        pearson=float(pearson_r),
        spearman=float(spearman_r),
        n_noticias=len(noticias_q),
    )

    try:
        db.session.add(correlacao)
        db.session.commit()
        logger.info(
            "%s: pearson=%.3f spearman=%.3f (%d notícias)",
            ativo.ticker, pearson_r, spearman_r, len(noticias_q),
        )
    except Exception as exc:
        db.session.rollback()
        logger.error("Erro ao salvar correlação de %s: %s", ativo.ticker, exc)
        raise

    return correlacao


def calcular_correlacao_todos(dias: int = 90) -> list[Correlacao]:
    """Recalcula correlação para todos os ativos cadastrados."""
    data_fim    = date.today()
    data_inicio = data_fim - timedelta(days=dias)
    resultados  = []

    for ativo in Ativo.query.all():
        c = calcular_correlacao(ativo, data_inicio, data_fim)
        if c:
            resultados.append(c)

    return resultados