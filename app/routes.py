from flask import Blueprint, render_template, redirect, url_for, request
from .models import Noticia
from .scraper import buscar_noticias
from . import db
from .repository import filtrar_noticias
from datetime import datetime, timedelta
import nltk
from nltk import trigrams
from nltk.corpus import stopwords
from collections import Counter
import os

nltk.data.path.append(os.path.join(os.path.dirname(__file__), '../nltk_data'))

bp = Blueprint('main', __name__)

@bp.route('/', methods=['GET'])
def index():
    data_filtro = request.args.get('data', None)
    assunto_filtro = request.args.get('assunto', None)
    periodo = request.args.get('periodo', None)
    page = request.args.get('page', default=1, type=int)  # Pega a página da URL
    
    noticias_paginadas = filtrar_noticias(data_filtro, assunto_filtro, periodo, page=page, per_page=15)
    return render_template('index.html', noticias=noticias_paginadas.items, pagination=noticias_paginadas)

@bp.route('/atualizar')
def atualizar():
    buscar_noticias()
    return redirect(url_for('main.index'))

@bp.route('/noticia/<int:id>')
def noticia_detalhe(id):
    noticia = Noticia.query.get_or_404(id)
    return render_template('noticia.html', noticia=noticia)

@bp.route('/dashboard', methods=['GET'])
def dashboard():
    data_filtro = request.args.get('data', None)
    assunto_filtro = request.args.get('assunto', None)
    periodo = request.args.get('periodo', None)
    
    noticias = filtrar_noticias(data_filtro, assunto_filtro, periodo)
    titulos = [n.titulo.lower() for n in noticias.items]
    stop_words = set(stopwords.words('portuguese'))
    palavras = []
    
    for titulo in titulos:
        tokens = nltk.word_tokenize(titulo)
        tokens = [t for t in tokens if t not in stop_words and len(t) > 3]
        trigramas = [' '.join(t) for t in trigrams(tokens)]
        palavras.extend(trigramas)
    
    contagem = Counter(palavras).most_common(5)
    top_assuntos = [{'assunto': a, 'frequencia': f} for a, f in contagem]
    
    return render_template('dashboard.html', top_assuntos=top_assuntos, data_filtro=data_filtro, assunto_filtro=assunto_filtro, periodo=periodo)