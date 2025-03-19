from flask import render_template, redirect, url_for, request
from .models import Noticia
from .scraper import buscar_noticias
from flask import current_app as app
from datetime import datetime, timedelta
from . import db
import nltk
from nltk import trigrams
from nltk.corpus import stopwords
from collections import Counter

@app.route('/', methods=['GET'])
def index():
    data_filtro = request.args.get('data', None)
    assunto_filtro = request.args.get('assunto', None)
    periodo = request.args.get('periodo', None)
    
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
    
    noticias = query.order_by(Noticia.data_publicacao.desc()).limit(15).all()
    return render_template('index.html', noticias=noticias)

@app.route('/atualizar')
def atualizar():
    buscar_noticias()
    return redirect(url_for('index'))

@app.route('/noticia/<int:id>')
def noticia_detalhe(id):
    noticia = Noticia.query.get_or_404(id)
    return render_template('noticia.html', noticia=noticia)

@app.route('/dashboard', methods=['GET'])
def dashboard():
    data_filtro = request.args.get('data', None)
    assunto_filtro = request.args.get('assunto', None)
    periodo = request.args.get('periodo', None)
    
    query = Noticia.query
    
    if data_filtro:
        try:
            data = datetime.strptime(data_filtro, '%Y-%m-%d')
            query = query.filter(db.func.date(Noticia.data_publicacao) >= data.date())
        except ValueError:
            pass
    
    if assunto_filtro:
        query = query.filter(
            (Noticia.titulo.ilike(f'%{assunto_filtro}%')) |
            (Noticia.conteudo.ilike(f'%{assunto_filtro}%'))
        )
    
    if periodo == 'semana':
        data_inicio = datetime.now() - timedelta(days=7)
        query = query.filter(Noticia.data_publicacao >= data_inicio)
    elif periodo == 'mes':
        data_inicio = datetime.now() - timedelta(days=30)
        query = query.filter(Noticia.data_publicacao >= data_inicio)
    
    noticias = query.all()
    titulos = [n.titulo.lower() for n in noticias]
    stop_words = set(stopwords.words('portuguese'))
    palavras = []
    
    for titulo in titulos:
        tokens = nltk.word_tokenize(titulo)
        tokens = [t for t in tokens if t not in stop_words and len(t) > 3]
        trigramas = [' '.join(t) for t in trigrams(tokens)]
        palavras.extend(trigramas)
    
    contagem = Counter(palavras).most_common(10)
    top_assuntos = [{'assunto': a, 'frequencia': f} for a, f in contagem]
    
    return render_template('dashboard.html', top_assuntos=top_assuntos, data_filtro=data_filtro, assunto_filtro=assunto_filtro, periodo=periodo)