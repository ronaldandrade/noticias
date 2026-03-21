from . import db
from datetime import datetime
from . import db

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



# Adicione estas classes ao seu arquivo models.py existente
# e o campo score_sentimento à sua classe Noticia

# ── Acrescente este campo à sua classe Noticia existente ──────────────────────



class Ativo(db.Model):
    """Representa um ativo financeiro monitorado (ex: PETR4, VALE3, BTC-USD)."""
    __tablename__ = "ativo"

    id     = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(20),  nullable=False, unique=True)   # ex: "PETR4.SA"
    nome   = db.Column(db.String(100), nullable=False)                 # ex: "Petrobras"
    setor  = db.Column(db.String(100), nullable=True)                  # ex: "Energia"

    cotacoes    = db.relationship("Cotacao",    backref="ativo", lazy="dynamic")
    correlacoes = db.relationship("Correlacao", backref="ativo", lazy="dynamic")

    def __repr__(self):
        return f"<Ativo {self.ticker}>"


class Cotacao(db.Model):
    """Preço diário de fechamento de um ativo (obtido via yfinance)."""
    __tablename__ = "cotacao"

    id               = db.Column(db.Integer, primary_key=True)
    ativo_id         = db.Column(db.Integer, db.ForeignKey("ativo.id"), nullable=False)
    data             = db.Column(db.Date,    nullable=False)
    preco_fechamento = db.Column(db.Float,   nullable=False)
    preco_abertura   = db.Column(db.Float,   nullable=True)
    variacao_pct     = db.Column(db.Float,   nullable=True)   # retorno diário em %
    volume           = db.Column(db.BigInteger, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("ativo_id", "data", name="uq_cotacao_ativo_data"),
    )

    def __repr__(self):
        return f"<Cotacao {self.ativo_id} {self.data} R${self.preco_fechamento}>"


class Correlacao(db.Model):
    """Resultado do cálculo de correlação sentimento × retorno para um período."""
    
    __tablename__ = "correlacao"

    id         = db.Column(db.Integer, primary_key=True)
    ativo_id   = db.Column(db.Integer, db.ForeignKey("ativo.id"), nullable=False)
    data_inicio = db.Column(db.Date,  nullable=False)
    data_fim    = db.Column(db.Date,  nullable=False)
    pearson    = db.Column(db.Float,  nullable=True)   # coef. de Pearson
    spearman   = db.Column(db.Float,  nullable=True)   # coef. de Spearman (mais robusto)
    n_noticias = db.Column(db.Integer, nullable=True)  # qtd de notícias no período
    criado_em  = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Correlacao ativo={self.ativo_id} pearson={self.pearson:.3f}>"