from functools import wraps
from flask import abort, jsonify, request, current_app
from flask_login import current_user
from .models import ApiKey


def require_admin(f):
    """Requer que o usuário logado tenha role='admin'."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def require_plan(*planos):
    """Requer que o usuário tenha um dos planos listados (ex: 'pro', 'enterprise').
    Admins sempre passam. Redireciona para /billing/planos se o plano for insuficiente.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            from flask import redirect, url_for, flash
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.is_admin:
                return f(*args, **kwargs)
            plano = current_user.plano_atual
            if plano and plano.nome in planos:
                return f(*args, **kwargs)
            flash("Este recurso requer um plano superior. Faça upgrade para continuar.", "info")
            return redirect(url_for("billing.planos"))
        return decorated
    return decorator


def require_api_key(f):
    """Autentica via header Authorization: Bearer <api_key> ou ?api_key=<key>."""
    @wraps(f)
    def decorated(*args, **kwargs):
        raw_key = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            raw_key = auth_header[7:].strip()
        if not raw_key:
            raw_key = request.args.get("api_key", "").strip()
        if not raw_key:
            return jsonify({"erro": "API key ausente. Use o header Authorization: Bearer <key>"}), 401

        api_key = ApiKey.verificar(raw_key)
        if not api_key:
            return jsonify({"erro": "API key inválida ou revogada."}), 401

        # Verifica se o plano do usuário tem acesso à API
        plano = api_key.user.plano_atual
        if not plano or not plano.acesso_api:
            return jsonify({"erro": "Seu plano não inclui acesso à API. Faça upgrade."}), 403

        # Atualiza estatísticas de uso
        from . import db
        from datetime import datetime
        api_key.ultima_uso = datetime.utcnow()
        api_key.total_requisicoes += 1
        db.session.commit()

        # Injeta o usuário no contexto da requisição
        request.api_user = api_key.user
        return f(*args, **kwargs)
    return decorated
