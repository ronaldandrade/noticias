from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from . import db, bcrypt
from .models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    return render_template("auth/login.html")


@auth_bp.post("/login")
def login_post():
    email = request.form.get("email", "").strip().lower()
    senha = request.form.get("senha", "")
    lembrar = bool(request.form.get("lembrar"))

    user = User.query.filter_by(email=email).first()

    if not user or not bcrypt.check_password_hash(user.password_hash, senha):
        flash("E-mail ou senha incorretos.", "error")
        return render_template("auth/login.html", email=email)

    login_user(user, remember=lembrar)
    next_page = request.args.get("next")
    return redirect(next_page or url_for("main.index"))


@auth_bp.get("/registro")
def registro():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    return render_template("auth/registro.html")


@auth_bp.post("/registro")
def registro_post():
    nome  = request.form.get("nome",  "").strip()
    email = request.form.get("email", "").strip().lower()
    senha = request.form.get("senha", "")
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

    login_user(user)
    return redirect(url_for("main.index"))


@auth_bp.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
