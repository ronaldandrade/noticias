import os


class Config:
    # ── Banco de dados ────────────────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///noticias.db")
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Segurança ─────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # ── Stripe (billing) ──────────────────────────────────────────────────────
    STRIPE_SECRET_KEY       = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY  = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET   = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_PRO        = os.environ.get("STRIPE_PRICE_PRO", "")
    STRIPE_PRICE_ENTERPRISE = os.environ.get("STRIPE_PRICE_ENTERPRISE", "")

    # ── E-mail (Flask-Mail) ───────────────────────────────────────────────────
    MAIL_SERVER   = os.environ.get("MAIL_SERVER",   "smtp.gmail.com")
    MAIL_PORT     = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS  = os.environ.get("MAIL_USE_TLS",  "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@monitorfinanceiro.com.br")

    # ── Limites por plano ─────────────────────────────────────────────────────
    PLAN_FREE_HISTORICO_DIAS = 7
    PLAN_FREE_MAX_ATIVOS     = 5
    PLAN_FREE_API_RATE       = "0/day"
    PLAN_PRO_HISTORICO_DIAS  = 90
    PLAN_PRO_MAX_ATIVOS      = -1   # sem limite
    PLAN_PRO_API_RATE        = "1000/day"
    PLAN_ENT_HISTORICO_DIAS  = 365
    PLAN_ENT_MAX_ATIVOS      = -1
    PLAN_ENT_API_RATE        = "10000/day"

    # ── Rate limiting geral ───────────────────────────────────────────────────
    RATELIMIT_DEFAULT        = "200/minute"
    RATELIMIT_STORAGE_URL    = os.environ.get("REDIS_URL", "memory://")
