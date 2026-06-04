import stripe
from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash, current_app
from flask_login import login_required, current_user
from . import db
from .models import Plan, Subscription, User

billing_bp = Blueprint("billing", __name__, url_prefix="/billing")


def _get_stripe():
    key = current_app.config.get("STRIPE_SECRET_KEY", "")
    if not key:
        return None
    stripe.api_key = key
    return stripe


# ── Página de planos ──────────────────────────────────────────────────────────

@billing_bp.get("/planos")
def planos():
    plans = Plan.query.order_by(Plan.preco_mensal).all()
    plano_atual = current_user.plano_atual if current_user.is_authenticated else None
    return render_template("billing/planos.html", plans=plans, plano_atual=plano_atual)


# ── Checkout (Stripe) ─────────────────────────────────────────────────────────

@billing_bp.post("/checkout/<string:plan_nome>")
@login_required
def checkout(plan_nome):
    s = _get_stripe()
    if not s:
        flash("Pagamentos indisponíveis no momento. Tente mais tarde.", "error")
        return redirect(url_for("billing.planos"))

    plan = Plan.query.filter_by(nome=plan_nome).first_or_404()
    if not plan.stripe_price_id:
        flash("Este plano não está disponível para compra online.", "error")
        return redirect(url_for("billing.planos"))

    # Cria ou recupera o customer no Stripe
    if not current_user.stripe_customer_id:
        customer = s.Customer.create(email=current_user.email, name=current_user.nome or "")
        current_user.stripe_customer_id = customer.id
        db.session.commit()

    try:
        session = s.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
            mode="subscription",
            success_url=url_for("billing.sucesso", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=url_for("billing.planos", _external=True),
            metadata={"user_id": current_user.id, "plan_nome": plan.nome},
        )
        return redirect(session.url, code=303)
    except s.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        flash("Erro ao iniciar pagamento. Tente novamente.", "error")
        return redirect(url_for("billing.planos"))


@billing_bp.get("/sucesso")
@login_required
def sucesso():
    flash("Assinatura ativada com sucesso! Bem-vindo ao plano Pro.", "info")
    return redirect(url_for("main.index"))


# ── Portal do cliente (gerenciar assinatura) ──────────────────────────────────

@billing_bp.post("/portal")
@login_required
def portal():
    s = _get_stripe()
    if not s or not current_user.stripe_customer_id:
        flash("Nenhuma assinatura ativa encontrada.", "error")
        return redirect(url_for("account.perfil"))

    try:
        session = s.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=url_for("account.perfil", _external=True),
        )
        return redirect(session.url, code=303)
    except s.error.StripeError as e:
        current_app.logger.error(f"Stripe portal error: {e}")
        flash("Erro ao abrir portal de cobrança.", "error")
        return redirect(url_for("account.perfil"))


# ── Webhook do Stripe ─────────────────────────────────────────────────────────

@billing_bp.post("/webhook")
def webhook():
    s = _get_stripe()
    if not s:
        return jsonify({"erro": "Stripe não configurado"}), 503

    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")
    webhook_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET", "")

    try:
        event = s.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, s.error.SignatureVerificationError):
        return jsonify({"erro": "Assinatura inválida"}), 400

    _processar_evento(event)
    return jsonify({"status": "ok"})


def _processar_evento(event):
    data = event["data"]["object"]

    if event["type"] == "checkout.session.completed":
        user_id  = int(data.get("metadata", {}).get("user_id", 0))
        plan_nome = data.get("metadata", {}).get("plan_nome", "")
        stripe_sub_id = data.get("subscription")
        _ativar_subscricao(user_id, plan_nome, stripe_sub_id)

    elif event["type"] == "customer.subscription.updated":
        _atualizar_status_subscricao(data)

    elif event["type"] in ("customer.subscription.deleted", "invoice.payment_failed"):
        _cancelar_subscricao(data)


def _ativar_subscricao(user_id, plan_nome, stripe_sub_id):
    user = User.query.get(user_id)
    plan = Plan.query.filter_by(nome=plan_nome).first()
    if not user or not plan:
        return

    sub_existente = Subscription.query.filter_by(user_id=user_id, status="active").first()
    if sub_existente:
        sub_existente.status = "canceled"

    nova_sub = Subscription(
        user_id=user_id,
        plan_id=plan.id,
        status="active",
        stripe_subscription_id=stripe_sub_id,
    )
    db.session.add(nova_sub)
    db.session.commit()


def _atualizar_status_subscricao(data):
    stripe_sub_id = data.get("id")
    novo_status = data.get("status")
    sub = Subscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first()
    if sub:
        sub.status = novo_status
        db.session.commit()


def _cancelar_subscricao(data):
    stripe_sub_id = data.get("id") or data.get("subscription")
    sub = Subscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first()
    if sub:
        sub.status = "canceled"
        db.session.commit()
