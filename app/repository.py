from .models import Noticia
from . import db
from datetime import datetime, timedelta

def filtrar_noticias(data_filtro=None, assunto_filtro=None, periodo=None, limit=None):
    query = Noticia.query
    
    if data_filtro:
        try:
            data = datetime.strptime(data_filtro, '%Y-%m-%d')
            query = query.filter(db.func.date(Noticia.data_publicacao) >= data.date())
        except ValueError:
            pass
    
    if assunto_filtro:
        palavras = assunto_filtro.split()
        for palavra in palavras:
            query = query.filter(
                (Noticia.titulo.ilike(f'%{palavra}%')) |
                (Noticia.conteudo.ilike(f'%{palavra}%'))
            )
    
    if periodo == 'semana':
        data_inicio = datetime.now() - timedelta(days=7)
        query = query.filter(Noticia.data_publicacao >= data_inicio)
    elif periodo == 'mes':
        data_inicio = datetime.now() - timedelta(days=30)
        query = query.filter(Noticia.data_publicacao >= data_inicio)
    
    if limit:
        return query.order_by(Noticia.data_publicacao.desc()).limit(limit).all()
    return query.order_by(Noticia.data_publicacao.desc()).all()