from . import db
from datetime import datetime


class Noticia(db.Model):
    __tablename__ = 'Noticia'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    url = db.Column(db.String(500), unique=True, nullable=False)
    data_publicacao = db.Column(db.DateTime, nullable=False)
    resumo = db.Column(db.Text)
    score_sentimento = db.Column(db.Float, nullable=True)
    categoria = db.Column(db.String(50), nullable=True)

    def __init__(self, titulo: str, conteudo: str, url: str, data_publicacao: datetime,
                 resumo: str | None = None, score_sentimento: float | None = None,
                 categoria: str | None = None):
        self.titulo = titulo
        self.conteudo = conteudo
        self.url = url
        self.data_publicacao = data_publicacao
        self.resumo = resumo
        self.score_sentimento = score_sentimento
        self.categoria = categoria
