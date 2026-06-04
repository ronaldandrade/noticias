from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from . import db, bcrypt
from .models import User, PasswordResetToken

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ── Login / Logout ────────────────────────────────────────────────────────────

@auth_bp.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    return render_template("auth/login.html")


@auth_bp.post("/login")
def login_post():
    email   = request.form.get("email", "").strip().lower()
    senha   = request.form.get("senha", "")
    lembrar = bool(request.form.get("lembrar"))

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, senha):
        flash("E-mail ou senha incorretos.", "error")
        return render_template("auth/login.html", email=email)

    login_user(user, remember=lembrar)
    next_page = request.args.get("next")
    return redirect(next_page or url_for("main.index"))


@auth_bp.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


# ── Registro ──────────────────────────────────────────────────────────────────

@auth_bp.get("/registro")
def registro():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    return render_template("auth/registro.html")


@auth_bp.post("/registro")
def registro_post():
    nome        = request.form.get("nome",        "").strip()
    email       = request.form.get("email",       "").strip().lower()
    senha       = request.form.get("senha",       "")
    confirmacao = request.form.get("confirmacao", "")

    if not email or not senha:
        flash("E-mail e senha são obrigatórios.", "error")
        return render_template("auth/registro.html", nome=nome, email=email)

    if senha != confirmacao:
        flash("As senhas não coincidem.", "error")
        return render_template("auth/registro.html", nome=nome, email=email)

    if len(senha) < 8:
        flash("A senha deve ter pelo menos 8 caracteres.", "error")
        return render_template("auth/registro.html", nome=nome, email=email)

    if User.query.filter_by(email=email).first():
        flash("Este e-mail já está cadastrado.", "error")
        return render_template("auth/registro.html", nome=nome, email=email)

    hash_senha = bcrypt.generate_password_hash(senha).decode("utf-8")
    user = User(email=email, password_hash=hash_senha, nome=nome or None)
    db.session.add(user)
    db.session.commit()

    _atribuir_plano_gratuito(user)

    login_user(user)
    return redirect(url_for("main.index"))


def _atribuir_plano_gratuito(user):
    from .models import Plan, Subscription
    plan_free = Plan.query.filter_by(nome="free").first()
    if plan_free:
        sub = Subscription(user_id=user.id, plan_id=plan_free.id, status="active")
        db.session.add(sub)
        db.session.commit()


# ── Recuperação de senha ──────────────────────────────────────────────────────

@auth_bp.get("/recuperar-senha")
def recuperar_senha():
    return render_template("auth/recuperar_senha.html")


@auth_bp.post("/recuperar-senha")
def recuperar_senha_post():
    email = request.form.get("email", "").strip().lower()
    user = User.query.filter_by(email=email).first()

    # Sempre exibe a mesma mensagem para não vazar se o e-mail existe
    flash("Se este e-mail estiver cadastrado, você receberá as instruções em breve.", "info")

    if user:
        raw_token, token_obj = PasswordResetToken.gerar(user.id)
        db.session.add(token_obj)
        db.session.commit()
        _enviar_email_reset(user, raw_token)

    return redirect(url_for("auth.login"))


@auth_bp.get("/redefinir-senha/<string:token>")
def redefinir_senha(token):
    token_obj = PasswordResetToken.verificar(token)
    if not token_obj or token_obj.expirado:
        flash("Link de redefinição inválido ou expirado.", "error")
        return redirect(url_for("auth.recuperar_senha"))
    return render_template("auth/redefinir_senha.html", token=token)


@auth_bp.post("/redefinir-senha/<string:token>")
def redefinir_senha_post(token):
    token_obj = PasswordResetToken.verificar(token)
    if not token_obj or token_obj.expirado:
        flash("Link de redefinição inválido ou expirado.", "error")
        return redirect(url_for("auth.recuperar_senha"))

    nova_senha  = request.form.get("senha", "")
    confirmacao = request.form.get("confirmacao", "")

    if nova_senha != confirmacao:
        flash("As senhas não coincidem.", "error")
        return render_template("auth/redefinir_senha.html", token=token)

    if len(nova_senha) < 8:
        flash("A senha deve ter pelo menos 8 caracteres.", "error")
        return render_template("auth/redefinir_senha.html", token=token)

    user = token_obj.user
    user.password_hash = bcrypt.generate_password_hash(nova_senha).decode("utf-8")
    token_obj.usado = True
    db.session.commit()

    flash("Senha redefinida com sucesso. Faça login.", "info")
    return redirect(url_for("auth.login"))


def _enviar_email_reset(user, raw_token):
    """Envia e-mail com link de reset. Em dev, imprime no log."""
    link = url_for("auth.redefinir_senha", token=raw_token, _external=True)
    try:
        from . import mail
        from flask_mail import Message
        msg = Message(
            subject="Redefinição de senha — Monitor Financeiro",
            recipients=[user.email],
            body=(
                f"Olá, {user.nome or 'usuário'}!\n\n"
                f"Clique no link abaixo para redefinir sua senha (válido por 2 horas):\n\n"
                f"{link}\n\n"
                f"Se você não solicitou isso, ignore este e-mail."
            ),
        )
        mail.send(msg)
    except Exception as e:
        current_app.logger.warning(f"E-mail de reset não enviado ({e}). Link: {link}")
