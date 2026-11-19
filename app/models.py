from . import db
from datetime import datetime


# ── Dados financeiros ───────────────────────────────────────────

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
