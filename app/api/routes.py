from flask import Blueprint, jsonify, request
from ..decorators import require_api_key
from ..models import Noticia, Ativo, Cotacao, Correlacao
from .. import db
from datetime import datetime, timedelta

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


# ── Utilitários ───────────────────────────────────────────────────────────────

def _parse_int(val, default, min_val=1, max_val=500):
    try:
        return max(min_val, min(int(val), max_val))
    except (TypeError, ValueError):
        return default


def _parse_date(val):
    try:
        return datetime.strptime(val, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@api_bp.get("/health")
def health():
    """Health check público (sem API key)."""
    return jsonify({"status": "ok", "version": "1.0"})


@api_bp.get("/noticias")
@require_api_key
def listar_noticias():
    """
    Retorna lista de notícias com sentimento.

    Query params:
      - page (int): página (default 1)
      - per_page (int): itens por página (default 20, max 100)
      - ativo (str): filtrar por ticker (ex: PETR4.SA)
      - categoria (str): filtrar por categoria
      - data_inicio (YYYY-MM-DD): filtrar por data inicial
      - data_fim (YYYY-MM-DD): filtrar por data final
      - score_min / score_max (float): filtrar por score de sentimento
    """
    page       = _parse_int(request.args.get("page"), 1)
    per_page   = _parse_int(request.args.get("per_page"), 20, max_val=100)
    ativo_ticker = request.args.get("ativo")
    categoria  = request.args.get("categoria")
    data_inicio = _parse_date(request.args.get("data_inicio"))
    data_fim   = _parse_date(request.args.get("data_fim"))
    score_min  = request.args.get("score_min", type=float)
    score_max  = request.args.get("score_max", type=float)

    q = Noticia.query

    if ativo_ticker:
        ativo = Ativo.query.filter_by(ticker=ativo_ticker).first()
        if not ativo:
            return jsonify({"erro": f"Ativo '{ativo_ticker}' não encontrado."}), 404
        q = q.filter_by(ativo_id=ativo.id)

    if categoria:
        q = q.filter_by(categoria=categoria)
    if data_inicio:
        q = q.filter(Noticia.data_publicacao >= data_inicio)
    if data_fim:
        q = q.filter(Noticia.data_publicacao <= data_fim + timedelta(days=1))
    if score_min is not None:
        q = q.filter(Noticia.score_sentimento >= score_min)
    if score_max is not None:
        q = q.filter(Noticia.score_sentimento <= score_max)

    resultado = q.order_by(Noticia.data_publicacao.desc()).paginate(page=page, per_page=per_page)

    ativos_map = {a.id: a for a in Ativo.query.all()}

    return jsonify({
        "pagina": resultado.page,
        "total_paginas": resultado.pages,
        "total_itens": resultado.total,
        "itens": [
            {
                "id": n.id,
                "titulo": n.titulo,
                "resumo": n.resumo,
                "url": n.url,
                "data_publicacao": n.data_publicacao.isoformat(),
                "score_sentimento": n.score_sentimento,
                "categoria": n.categoria,
                "ativo": ativos_map[n.ativo_id].ticker if n.ativo_id and n.ativo_id in ativos_map else None,
            }
            for n in resultado.items
        ],
    })


@api_bp.get("/ativos")
@require_api_key
def listar_ativos():
    """Retorna todos os ativos monitorados."""
    ativos = Ativo.query.order_by(Ativo.ticker).all()
    return jsonify([
        {"id": a.id, "ticker": a.ticker, "nome": a.nome, "setor": a.setor}
        for a in ativos
    ])


@api_bp.get("/ativos/<string:ticker>/sentimento")
@require_api_key
def sentimento_ativo(ticker):
    """
    Retorna série temporal de sentimento médio diário para um ativo.

    Query params:
      - dias (int): janela em dias (default 30, max 365)
    """
    ativo = Ativo.query.filter_by(ticker=ticker).first()
    if not ativo:
        return jsonify({"erro": f"Ativo '{ticker}' não encontrado."}), 404

    dias = _parse_int(request.args.get("dias"), 30, max_val=365)
    desde = datetime.utcnow() - timedelta(days=dias)

    rows = (
        db.session.query(
            db.func.date(Noticia.data_publicacao).label("data"),
            db.func.avg(Noticia.score_sentimento).label("score_medio"),
            db.func.count(Noticia.id).label("total"),
        )
        .filter(Noticia.ativo_id == ativo.id, Noticia.data_publicacao >= desde)
        .group_by(db.func.date(Noticia.data_publicacao))
        .order_by(db.func.date(Noticia.data_publicacao))
        .all()
    )

    return jsonify({
        "ticker": ativo.ticker,
        "nome": ativo.nome,
        "dias": dias,
        "serie": [
            {"data": str(r.data), "score_medio": round(r.score_medio, 4), "total_noticias": r.total}
            for r in rows
        ],
    })


@api_bp.get("/ativos/<string:ticker>/correlacao")
@require_api_key
def correlacao_ativo(ticker):
    """Retorna a correlação mais recente sentimento × retorno para um ativo."""
    ativo = Ativo.query.filter_by(ticker=ticker).first()
    if not ativo:
        return jsonify({"erro": f"Ativo '{ticker}' não encontrado."}), 404

    corr = (
        Correlacao.query
        .filter_by(ativo_id=ativo.id)
        .order_by(Correlacao.criado_em.desc())
        .first()
    )

    if not corr:
        return jsonify({"erro": "Nenhuma correlação calculada para este ativo."}), 404

    return jsonify({
        "ticker": ativo.ticker,
        "pearson": corr.pearson,
        "spearman": corr.spearman,
        "n_noticias": corr.n_noticias,
        "periodo": {"inicio": str(corr.data_inicio), "fim": str(corr.data_fim)},
        "calculado_em": corr.criado_em.isoformat(),
    })


@api_bp.get("/ativos/<string:ticker>/cotacoes")
@require_api_key
def cotacoes_ativo(ticker):
    """
    Retorna preços históricos de um ativo.

    Query params:
      - dias (int): janela em dias (default 30, max 365)
    """
    ativo = Ativo.query.filter_by(ticker=ticker).first()
    if not ativo:
        return jsonify({"erro": f"Ativo '{ticker}' não encontrado."}), 404

    dias = _parse_int(request.args.get("dias"), 30, max_val=365)
    desde = datetime.utcnow().date() - timedelta(days=dias)

    cotacoes = (
        Cotacao.query
        .filter(Cotacao.ativo_id == ativo.id, Cotacao.data >= desde)
        .order_by(Cotacao.data)
        .all()
    )

    return jsonify({
        "ticker": ativo.ticker,
        "nome": ativo.nome,
        "cotacoes": [
            {
                "data": str(c.data),
                "fechamento": c.preco_fechamento,
                "abertura": c.preco_abertura,
                "variacao_pct": c.variacao_pct,
                "volume": c.volume,
            }
            for c in cotacoes
        ],
    })
