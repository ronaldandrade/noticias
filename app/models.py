from . import db

class Noticia(db.Model):
    __tablename__ = 'Noticia'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    url = db.Column(db.String(500), unique=True, nullable=False)
    data_publicacao = db.Column(db.DateTime, nullable=False)