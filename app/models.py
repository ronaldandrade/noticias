from . import db
from datetime import datetime, timedelta
from flask_login import UserMixin
import secrets
import hashlib


# ── Planos ────────────────────────────────────────────────────────────────────

class Plan(db.Model):
    __tablename__ = "plan"

    id                  = db.Column(db.Integer, primary_key=True)
    nome                = db.Column(db.String(50), unique=True, nullable=False)  # "free","pro","enterprise"
    display_nome        = db.Column(db.String(100), nullable=False)
    preco_mensal        = db.Column(db.Float, nullable=False, default=0.0)
    stripe_price_id     = db.Column(db.String(100), nullable=True)
    max_ativos          = db.Column(db.Integer, nullable=False, default=5)       # -1 = ilimitado
    historico_dias      = db.Column(db.Integer, nullable=False, default=7)
    acesso_api          = db.Column(db.Boolean, nullable=False, default=False)
    acesso_relatorio    = db.Column(db.Boolean, nullable=False, default=False)
    acesso_termometro   = db.Column(db.Boolean, nullable=False, default=False)
    acesso_dashboard    = db.Column(db.Boolean, nullable=False, default=True)

    subscriptions = db.relationship("Subscription", backref="plan", lazy="dynamic")

    def __repr__(self):
        return f"<Plan {self.nome}>"


# ── Usuários ──────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = "user"

    id                 = db.Column(db.Integer, primary_key=True)
    email              = db.Column(db.String(150), unique=True, nullable=False)
    password_hash      = db.Column(db.String(256), nullable=False)
    nome               = db.Column(db.String(100), nullable=True)
    role               = db.Column(db.String(20), nullable=False, default="user")  # "user" | "admin"
    email_verificado   = db.Column(db.Boolean, nullable=False, default=False)
    stripe_customer_id = db.Column(db.String(100), nullable=True)
    criado_em          = db.Column(db.DateTime, default=datetime.utcnow)

    subscriptions      = db.relationship("Subscription", backref="user", lazy="dynamic")
    api_keys           = db.relationship("ApiKey", backref="user", lazy="dynamic")
    reset_tokens       = db.relationship("PasswordResetToken", backref="user", lazy="dynamic")

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def subscription_ativa(self):
        return (
            Subscription.query
            .filter_by(user_id=self.id, status="active")
            .order_by(Subscription.criado_em.desc())
            .first()
        )

    @property
    def plano_atual(self):
        sub = self.subscription_ativa
        if sub:
            return sub.plan
        return Plan.query.filter_by(nome="free").first()

    def __repr__(self):
        return f"<User {self.email}>"


# ── Assinaturas ───────────────────────────────────────────────────────────────

class Subscription(db.Model):
    __tablename__ = "subscription"

    id                      = db.Column(db.Integer, primary_key=True)
    user_id                 = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    plan_id                 = db.Column(db.Integer, db.ForeignKey("plan.id"), nullable=False)
    status                  = db.Column(db.String(20), nullable=False, default="active")  # active|canceled|past_due|trialing
    stripe_subscription_id  = db.Column(db.String(100), nullable=True)
    periodo_inicio          = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    periodo_fim             = db.Column(db.DateTime, nullable=True)
    criado_em               = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em           = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Subscription user={self.user_id} plan={self.plan_id} status={self.status}>"


# ── API Keys ──────────────────────────────────────────────────────────────────

class ApiKey(db.Model):
    __tablename__ = "api_key"

    id                  = db.Column(db.Integer, primary_key=True)
    user_id             = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    nome                = db.Column(db.String(100), nullable=False)
    key_hash            = db.Column(db.String(256), nullable=False, unique=True)
    key_prefix          = db.Column(db.String(12), nullable=False)
    ultima_uso          = db.Column(db.DateTime, nullable=True)
    total_requisicoes   = db.Column(db.Integer, nullable=False, default=0)
    ativo               = db.Column(db.Boolean, nullable=False, default=True)
    criado_em           = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def gerar():
        """Retorna (raw_key, key_hash, key_prefix) — raw_key mostrado só uma vez."""
        raw = "mf_" + secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw.encode()).hexdigest()
        key_prefix = raw[:12]
        return raw, key_hash, key_prefix

    @staticmethod
    def verificar(raw_key):
        """Busca ApiKey pelo hash do raw_key. Retorna ApiKey ou None."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        return ApiKey.query.filter_by(key_hash=key_hash, ativo=True).first()

    def __repr__(self):
        return f"<ApiKey {self.key_prefix}... user={self.user_id}>"


# ── Recuperação de senha ──────────────────────────────────────────────────────

class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_token"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    token_hash = db.Column(db.String(256), nullable=False, unique=True)
    expira_em  = db.Column(db.DateTime, nullable=False)
    usado      = db.Column(db.Boolean, nullable=False, default=False)
    criado_em  = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def gerar(user_id, horas=2):
        raw = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        expira_em = datetime.utcnow() + timedelta(hours=horas)
        token = PasswordResetToken(user_id=user_id, token_hash=token_hash, expira_em=expira_em)
        return raw, token

    @staticmethod
    def verificar(raw_token):
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        return PasswordResetToken.query.filter_by(token_hash=token_hash, usado=False).first()

    @property
    def expirado(self):
        return datetime.utcnow() > self.expira_em

    def __repr__(self):
        return f"<PasswordResetToken user={self.user_id} expirado={self.expirado}>"


# ── Dados financeiros (inalterados) ───────────────────────────────────────────

class Noticia(db.Model):
    __tablename__ = 'Noticia'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    url = db.Column(db.String(500), unique=True, nullable=False)
    data_publicacao = db.Column(db.DateTime, nullable=False)
    resumo = db.Column(db.Text)
    score_sentimento = db.Column(db.Float, nullable=True)
    ativo_id         = db.Column(db.Integer, db.ForeignKey('ativo.id'), nullable=True)
    categoria = db.Column(db.String(50), nullable=True)

    def __init__(self, titulo: str, conteudo: str, url: str, data_publicacao: datetime,
                 resumo: str | None = None, score_sentimento: float | None = None,
                 ativo_id: int | None = None, categoria: str | None = None):
        self.titulo = titulo
        self.conteudo = conteudo
        self.url = url
        self.data_publicacao = data_publicacao
        self.resumo = resumo
        self.score_sentimento = score_sentimento
        self.ativo_id = ativo_id
        self.categoria = categoria


class Ativo(db.Model):
    __tablename__ = "ativo"

    id     = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(20),  nullable=False, unique=True)
    nome   = db.Column(db.String(100), nullable=False)
    setor  = db.Column(db.String(100), nullable=True)

    cotacoes    = db.relationship("Cotacao",    backref="ativo", lazy="dynamic")
    correlacoes = db.relationship("Correlacao", backref="ativo", lazy="dynamic")

    def __init__(self, ticker: str, nome: str, setor: str | None = None):
        self.ticker = ticker
        self.nome = nome
        self.setor = setor

    def __repr__(self):
        return f"<Ativo {self.ticker}>"


class Cotacao(db.Model):
    __tablename__ = "cotacao"

    id               = db.Column(db.Integer, primary_key=True)
    ativo_id         = db.Column(db.Integer, db.ForeignKey("ativo.id"), nullable=False)
    data             = db.Column(db.Date,    nullable=False)
    preco_fechamento = db.Column(db.Float,   nullable=False)
    preco_abertura   = db.Column(db.Float,   nullable=True)
    variacao_pct     = db.Column(db.Float,   nullable=True)
    volume           = db.Column(db.BigInteger, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("ativo_id", "data", name="uq_cotacao_ativo_data"),
    )

    def __repr__(self):
        return f"<Cotacao {self.ativo_id} {self.data} R${self.preco_fechamento}>"


class Correlacao(db.Model):
    __tablename__ = "correlacao"

    id          = db.Column(db.Integer, primary_key=True)
    ativo_id    = db.Column(db.Integer, db.ForeignKey("ativo.id"), nullable=False)
    data_inicio = db.Column(db.Date,  nullable=False)
    data_fim    = db.Column(db.Date,  nullable=False)
    pearson     = db.Column(db.Float,  nullable=True)
    spearman    = db.Column(db.Float,  nullable=True)
    n_noticias  = db.Column(db.Integer, nullable=True)
    criado_em   = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Correlacao ativo={self.ativo_id} pearson={self.pearson:.3f}>"


# ── Ativos favoritos do usuário ───────────────────────────────────────────────

class UserFavoriteAsset(db.Model):
    __tablename__ = "user_favorite_asset"

    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    symbol   = db.Column(db.String(20),  nullable=False)
    nome     = db.Column(db.String(100), nullable=True)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "symbol", name="uq_user_favorite_symbol"),
    )

    def __repr__(self):
        return f"<UserFavoriteAsset user={self.user_id} symbol={self.symbol}>"
