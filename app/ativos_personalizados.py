"""
Blueprint: Ativos Personalizados
Watchlist page + REST endpoints for user favorite assets.
"""
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user

from .models import UserFavoriteAsset, db
from .services.ativos_service import (
    DEFAULT_ASSETS,
    fetch_price_batch,
    fetch_ytd,
    get_sentiment_for_symbol,
    get_noticias_for_symbol,
    buscar_b3,
)

ativos_bp = Blueprint("ativos", __name__, url_prefix="/meus-ativos")


# ── Página principal ──────────────────────────────────────────────────────────

@ativos_bp.get("/")
def index():
    user_assets = []
    user_count  = 0
    max_ativos  = 5

    if current_user.is_authenticated:
        favs = (
            UserFavoriteAsset.query
            .filter_by(user_id=current_user.id)
            .order_by(UserFavoriteAsset.added_at)
            .all()
        )
        user_assets = [{"symbol": f.symbol, "nome": f.nome or f.symbol} for f in favs]
        user_count  = len(favs)

        plan = current_user.plano_atual
        max_ativos = getattr(plan, "max_ativos", 5) if plan else 5

    return render_template(
        "meus_ativos.html",
        default_assets=DEFAULT_ASSETS,
        user_assets=user_assets,
        user_count=user_count,
        max_ativos=max_ativos,
    )


# ── API: dados de mercado ─────────────────────────────────────────────────────

@ativos_bp.get("/api/dados")
def api_dados():
    """Retorna preço, variação, volume e sparkline para uma lista de símbolos."""
    raw = request.args.get("symbols", "")
    if not raw:
        return jsonify({"error": "symbols obrigatório"}), 400

    symbols = [s.strip() for s in raw.split(",") if s.strip()][:25]
    price_data = fetch_price_batch(symbols)

    result = {}
    for sym in symbols:
        p   = price_data.get(sym)
        sent = get_sentiment_for_symbol(sym)

        result[sym] = {
            "preco":              p["preco"]    if p else None,
            "variacao":           p["variacao"] if p else None,
            "volume":             p["volume"]   if p else None,
            "sparkline_7d":       p["sparkline_7d"]       if p else [],
            "sparkline_7d_labels":p["sparkline_7d_labels"] if p else [],
            "sparkline_30d":      p["sparkline_30d"]       if p else [],
            "sparkline_30d_labels":p["sparkline_30d_labels"] if p else [],
            "score_7d":           sent["score_7d"]   if sent else None,
            "score_30d":          sent["score_30d"]  if sent else None,
            "n_noticias":         sent["n_noticias"] if sent else 0,
            "pearson":            sent["pearson"]    if sent else None,
        }

    return jsonify(result)


@ativos_bp.get("/api/historico/<symbol>")
def api_historico(symbol):
    """Retorna histórico YTD de preços para o modal de detalhes."""
    data = fetch_ytd(symbol)
    if not data:
        return jsonify({"error": "sem dados"}), 404
    return jsonify(data)


@ativos_bp.get("/api/noticias/<symbol>")
def api_noticias(symbol):
    """Retorna últimas notícias de um ativo B3."""
    noticias = get_noticias_for_symbol(symbol, limit=8)
    return jsonify(noticias)


@ativos_bp.get("/api/buscar")
def api_buscar():
    """Busca ativos B3 por ticker ou nome."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    return jsonify(buscar_b3(q))


# ── API: favoritos do usuário ─────────────────────────────────────────────────

@ativos_bp.get("/api/favoritos")
@login_required
def listar_favoritos():
    favs = (
        UserFavoriteAsset.query
        .filter_by(user_id=current_user.id)
        .order_by(UserFavoriteAsset.added_at)
        .all()
    )
    return jsonify([
        {"symbol": f.symbol, "nome": f.nome, "added_at": f.added_at.isoformat()}
        for f in favs
    ])


@ativos_bp.post("/api/favoritos")
@login_required
def adicionar_favorito():
    data   = request.get_json(silent=True) or {}
    symbol = (data.get("symbol") or "").upper().strip()
    nome   = (data.get("nome")   or symbol).strip()

    if not symbol or len(symbol) > 20:
        return jsonify({"error": "Símbolo inválido"}), 400

    plan       = current_user.plano_atual
    max_ativos = getattr(plan, "max_ativos", 5) if plan else 5
    count      = UserFavoriteAsset.query.filter_by(user_id=current_user.id).count()

    if max_ativos != -1 and count >= max_ativos:
        plan_nome = plan.nome if plan else "free"
        return jsonify({"error": f"Limite de {max_ativos} ativos no plano {plan_nome}"}), 403

    if UserFavoriteAsset.query.filter_by(user_id=current_user.id, symbol=symbol).first():
        return jsonify({"error": "Ativo já adicionado"}), 409

    fav = UserFavoriteAsset(user_id=current_user.id, symbol=symbol, nome=nome)
    db.session.add(fav)
    db.session.commit()

    return jsonify({"ok": True, "symbol": symbol, "nome": nome}), 201


@ativos_bp.delete("/api/favoritos/<symbol>")
@login_required
def remover_favorito(symbol):
    fav = UserFavoriteAsset.query.filter_by(
        user_id=current_user.id,
        symbol=symbol.upper(),
    ).first_or_404()

    db.session.delete(fav)
    db.session.commit()

    return jsonify({"ok": True})
