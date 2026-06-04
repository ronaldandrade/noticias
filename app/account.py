from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from . import db, bcrypt
from .models import ApiKey, User

account_bp = Blueprint("account", __name__, url_prefix="/account")


@account_bp.get("/perfil")
@login_required
def perfil():
    api_keys = ApiKey.query.filter_by(user_id=current_user.id).order_by(ApiKey.criado_em.desc()).all()
    subscription = current_user.subscription_ativa
    plano = current_user.plano_atual
    return render_template("account/perfil.html", api_keys=api_keys, subscription=subscription, plano=plano)


@account_bp.post("/perfil")
@login_required
def perfil_update():
    nome = request.form.get("nome", "").strip()
    if nome:
        current_user.nome = nome
        db.session.commit()
        flash("Perfil atualizado.", "info")
    return redirect(url_for("account.perfil"))


@account_bp.post("/alterar-senha")
@login_required
def alterar_senha():
    senha_atual = request.form.get("senha_atual", "")
    nova_senha  = request.form.get("nova_senha", "")
    confirmacao = request.form.get("confirmacao", "")

    if not bcrypt.check_password_hash(current_user.password_hash, senha_atual):
        flash("Senha atual incorreta.", "error")
        return redirect(url_for("account.perfil"))

    if nova_senha != confirmacao:
        flash("As senhas não coincidem.", "error")
        return redirect(url_for("account.perfil"))

    if len(nova_senha) < 8:
        flash("A nova senha deve ter pelo menos 8 caracteres.", "error")
        return redirect(url_for("account.perfil"))

    current_user.password_hash = bcrypt.generate_password_hash(nova_senha).decode("utf-8")
    db.session.commit()
    flash("Senha alterada com sucesso.", "info")
    return redirect(url_for("account.perfil"))


# ── API Keys ──────────────────────────────────────────────────────────────────

@account_bp.post("/api-keys")
@login_required
def criar_api_key():
    plano = current_user.plano_atual
    if not plano or not plano.acesso_api:
        flash("Seu plano não inclui acesso à API. Faça upgrade.", "error")
        return redirect(url_for("account.perfil"))

    nome = request.form.get("nome", "").strip()
    if not nome:
        flash("Informe um nome para identificar a API key.", "error")
        return redirect(url_for("account.perfil"))

    existing = ApiKey.query.filter_by(user_id=current_user.id, ativo=True).count()
    MAX_KEYS = 10
    if existing >= MAX_KEYS:
        flash(f"Limite de {MAX_KEYS} API keys ativas atingido.", "error")
        return redirect(url_for("account.perfil"))

    raw_key, key_hash, key_prefix = ApiKey.gerar()
    api_key = ApiKey(user_id=current_user.id, nome=nome, key_hash=key_hash, key_prefix=key_prefix)
    db.session.add(api_key)
    db.session.commit()

    flash(f"API key criada. Copie agora — ela não será exibida novamente: {raw_key}", "api_key")
    return redirect(url_for("account.perfil"))


@account_bp.post("/api-keys/<int:key_id>/revogar")
@login_required
def revogar_api_key(key_id):
    api_key = ApiKey.query.filter_by(id=key_id, user_id=current_user.id).first_or_404()
    api_key.ativo = False
    db.session.commit()
    flash("API key revogada.", "info")
    return redirect(url_for("account.perfil"))
