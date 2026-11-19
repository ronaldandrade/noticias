from flask import Blueprint, jsonify, request
from ..models import Noticia
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
def listar_noticias():
    """
    Retorna lista de notícias com sentimento.

    Query params:
      - page (int): página (default 1)
      - per_page (int): itens por página (default 20, max 100)
      - categoria (str): filtrar por categoria
      - data_inicio (YYYY-MM-DD): filtrar por data inicial
      - data_fim (YYYY-MM-DD): filtrar por data final
      - score_min / score_max (float): filtrar por score de sentimento
    """
    page       = _parse_int(request.args.get("page"), 1)
    per_page   = _parse_int(request.args.get("per_page"), 20, max_val=100)
    categoria  = request.args.get("categoria")
    data_inicio = _parse_date(request.args.get("data_inicio"))
    data_fim   = _parse_date(request.args.get("data_fim"))
    score_min  = request.args.get("score_min", type=float)
    score_max  = request.args.get("score_max", type=float)

    q = Noticia.query

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
            }
            for n in resultado.items
        ],
    })
