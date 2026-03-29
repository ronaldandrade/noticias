from .models import Noticia
from . import db
from datetime import datetime, timedelta
from flask import request

def filtrar_noticias(data_filtro=None, assunto_filtro=None, periodo=None, page=1, per_page=10):
    query = Noticia.query

    categoria_filtro = request.args.get('categoria', None)
    
    if data_filtro:
        try:
            data = datetime.strptime(data_filtro, '%Y-%m-%d')
            query = query.filter(db.func.date(Noticia.data_publicacao) >= data.date())
        except ValueError:
            pass
    
    if categoria_filtro:
        query = query.filter(Noticia.categoria == categoria_filtro)
        
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
    
    return query.order_by(Noticia.data_publicacao.desc()).paginate(page=page, per_page=per_page)