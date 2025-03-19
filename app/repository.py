# from .models import Noticia
# from . import db
# from datetime import datetime, timedelta
# import nltk
# from nltk import trigrams
# from nltk.corpus import stopwords
# from collections import Counter

# def filtrar_noticias(data_filtro=None, assunto_filtro=None, periodo=None, limit=None):
#     query = Noticia.query
    
#     if data_filtro:
#         try:
#             data = datetime.strptime(data_filtro, '%Y-%m-%d')
#             query = query.filter(db.func.date(Noticia.data_publicacao) >= data.date())
#         except ValueError:
#             pass
    
#     if assunto_filtro:
#         palavras = assunto_filtro.split()
#         for palavra in palavras:
#             query = query.filter(
#                 (Noticia.titulo.ilike(f'%{palavra}%')) |
#                 (Noticia.conteudo.ilike(f'%{palavra}%'))
#             )
    
#     if periodo == 'semana':
#         data_inicio = datetime.now() - timedelta(days=7)
#         query = query.filter(Noticia.data_publicacao >= data_inicio)
#     elif periodo == 'mes':
#         data_inicio = datetime.now() - timedelta(days=30)
#         query = query.filter(Noticia.data_publicacao >= data_inicio)
    
#     if limit:
#         return query.order_by(Noticia.data_publicacao.desc()).limit(limit).all()
#     return query.order_by(Noticia.data_publicacao.desc()).all()

# def top_assuntos_noticias(data_filtro=None, assunto_filtro=None, periodo=None):
#     noticias = filtrar_noticias(data_filtro, assunto_filtro, periodo)
#     titulos = [n.titulo.lower() for n in noticias]
#     stop_words = set(stopwords.words('portuguese'))
#     palavras = []
    
#     for titulo in titulos:
#         tokens = nltk.word_tokenize(titulo)
#         tokens = [t for t in tokens if t not in stop_words and len(t) > 3]
#         trigramas = [' '.join(t) for t in trigrams(tokens)]
#         palavras.extend(trigramas)
    
#     contagem = Counter(palavras).most_common(10)
#     return [{'assunto': a, 'frequencia': f} for a, f in contagem]