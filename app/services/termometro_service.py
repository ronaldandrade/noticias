"""
services/termometro_service.py

Calcula o estado de sentimento atual de cada ativo e detecta
viradas em relação ao dia anterior e à média histórica.
"""

from datetime import date, timedelta, datetime
from collections import defaultdict

from ..models import Noticia, Ativo, Cotacao
from .. import db


def _score_medio_periodo(ativo_id: int, data_inicio: date, data_fim: date) -> float | None:
    """Score médio de sentimento de um ativo em um período."""
    rows = (
        db.session.query(Noticia.score_sentimento)
        .filter(
            Noticia.ativo_id == ativo_id,
            Noticia.score_sentimento.isnot(None),
            Noticia.data_publicacao >= data_inicio,
            Noticia.data_publicacao < data_fim + timedelta(days=1),
        )
        .all()
    )
    scores = [r[0] for r in rows]
    return round(sum(scores) / len(scores), 4) if scores else None


def _noticias_do_dia(ativo_id: int, dia: date) -> list[dict]:
    """Retorna as últimas notícias de um ativo em um dia específico."""
    noticias = (
        Noticia.query
        .filter(
            Noticia.ativo_id == ativo_id,
            Noticia.score_sentimento.isnot(None),
            Noticia.data_publicacao >= dia,
            Noticia.data_publicacao < dia + timedelta(days=1),
        )
        .order_by(Noticia.data_publicacao.desc())
        .limit(3)
        .all()
    )
    return [
        {
            "titulo": n.titulo,
            "score":  n.score_sentimento,
            "classe": _classe(n.score_sentimento),
            "url":    n.url,
            "hora":   n.data_publicacao.strftime("%H:%M"),
        }
        for n in noticias
    ]


def _classe(score: float | None) -> str:
    if score is None:
        return "neutro"
    if score > 0.05:
        return "positivo"
    if score < -0.05:
        return "negativo"
    return "neutro"


def _variacao_label(atual: float | None, anterior: float | None) -> dict:
    """Calcula a variação e detecta virada de sentimento."""
    if atual is None or anterior is None:
        return {"delta": None, "virada": False, "direcao": "neutro"}

    delta = round(atual - anterior, 4)
    virada = False
    direcao = "neutro"

    # Virada: mudança de classe (positivo→negativo ou vice-versa)
    if _classe(anterior) != _classe(atual):
        if _classe(anterior) in ("positivo", "neutro") and _classe(atual) == "negativo":
            virada = True
            direcao = "queda"
        elif _classe(anterior) in ("negativo", "neutro") and _classe(atual) == "positivo":
            virada = True
            direcao = "alta"

    if not virada:
        direcao = "alta" if delta > 0 else "queda" if delta < 0 else "neutro"

    return {"delta": delta, "virada": virada, "direcao": direcao}


def _ultima_cotacao(ativo_id: int) -> dict | None:
    """Última cotação disponível do ativo."""
    c = (
        Cotacao.query
        .filter_by(ativo_id=ativo_id)
        .filter(Cotacao.variacao_pct.isnot(None))
        .order_by(Cotacao.data.desc())
        .first()
    )
    if not c:
        return None
    return {
        "preco":      c.preco_fechamento,
        "variacao":   c.variacao_pct,
        "data":       c.data.strftime("%d/%m"),
        "classe":     "positivo" if c.variacao_pct > 0 else "negativo" if c.variacao_pct < 0 else "neutro",
    }


def gerar_termometro() -> dict:
    """
    Gera os dados completos do termômetro para todos os ativos com notícias recentes.

    Retorna:
        - ativos: lista ordenada por score do dia (mais negativo primeiro)
        - resumo: totais e contagem de viradas
        - gerado_em: timestamp
    """
    hoje      = date.today()
    ontem     = hoje - timedelta(days=1)
    semana    = hoje - timedelta(days=7)
    mes       = hoje - timedelta(days=30)

    # Se hoje não tem notícias (fim de semana / feriado), usa o último dia com dados
    ultimo_dia_query = (
        db.session.query(
            db.func.date(Noticia.data_publicacao).label("dia")
        )
        .filter(Noticia.score_sentimento.isnot(None))
        .order_by(db.func.date(Noticia.data_publicacao).desc())
        .first()
    )
    dia_referencia = ultimo_dia_query.dia if ultimo_dia_query else hoje
    if isinstance(dia_referencia, str):
        dia_referencia = date.fromisoformat(dia_referencia)

    dia_anterior = dia_referencia - timedelta(days=1)

    ativos = Ativo.query.all()
    resultado = []

    for ativo in ativos:
        score_hoje     = _score_medio_periodo(ativo.id, dia_referencia, dia_referencia)
        score_ontem    = _score_medio_periodo(ativo.id, dia_anterior,   dia_anterior)
        score_semana   = _score_medio_periodo(ativo.id, semana,         dia_referencia)
        score_mes      = _score_medio_periodo(ativo.id, mes,            dia_referencia)

        # Só inclui ativos com notícias recentes (última semana)
        if score_semana is None:
            continue

        variacao = _variacao_label(score_hoje, score_ontem)
        noticias_hoje = _noticias_do_dia(ativo.id, dia_referencia)

        n_hoje = (
            Noticia.query
            .filter(
                Noticia.ativo_id == ativo.id,
                Noticia.data_publicacao >= dia_referencia,
                Noticia.data_publicacao < dia_referencia + timedelta(days=1),
            )
            .count()
        )

        resultado.append({
            "ticker":        ativo.ticker.replace(".SA", ""),
            "ticker_full":   ativo.ticker,
            "nome":          ativo.nome,
            "setor":         ativo.setor or "—",
            "score_hoje":    score_hoje,
            "score_ontem":   score_ontem,
            "score_semana":  score_semana,
            "score_mes":     score_mes,
            "classe_hoje":   _classe(score_hoje or score_semana),
            "variacao":      variacao,
            "n_noticias":    n_hoje,
            "noticias":      noticias_hoje,
            "cotacao":       _ultima_cotacao(ativo.id),
        })

    # Ordena: viradas primeiro, depois por score absoluto (mais extremo primeiro)
    resultado.sort(key=lambda x: (
        -int(x["variacao"]["virada"]),
        abs(x["score_hoje"] or x["score_semana"] or 0)
    ), reverse=False)

    resultado.sort(key=lambda x: (
        -int(x["variacao"]["virada"]),
        -abs((x["score_hoje"] or x["score_semana"] or 0))
    ))

    # Resumo geral
    com_score = [a for a in resultado if a["score_hoje"] is not None]
    viradas   = [a for a in resultado if a["variacao"]["virada"]]

    score_mercado = (
        round(sum(a["score_hoje"] for a in com_score) / len(com_score), 3)
        if com_score else None
    )

    resumo = {
        "ativos_ativos":   len(resultado),
        "viradas":         len(viradas),
        "score_mercado":   score_mercado,
        "classe_mercado":  _classe(score_mercado),
        "positivos":       sum(1 for a in com_score if a["classe_hoje"] == "positivo"),
        "negativos":       sum(1 for a in com_score if a["classe_hoje"] == "negativo"),
        "neutros":         sum(1 for a in com_score if a["classe_hoje"] == "neutro"),
        "dia_referencia":  dia_referencia.strftime("%d/%m/%Y"),
        "eh_hoje":         dia_referencia == hoje,
    }

    return {
        "ativos":    resultado,
        "resumo":    resumo,
        "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }