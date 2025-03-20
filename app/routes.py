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
from .services import calcular_top_assuntos
import os

nltk.data.path.append(os.path.join(os.path.dirname(__file__), '../nltk_data'))

bp = Blueprint('main', __name__)

@bp.route('/', methods=['GET'])
def index():
    data_filtro = request.args.get('data', None)
    assunto_filtro = request.args.get('assunto', None)
    periodo = request.args.get('periodo', None)
    noticias = filtrar_noticias(data_filtro, assunto_filtro, periodo, limit=15)
    return render_template('index.html', noticias=noticias)

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
    top_assuntos = calcular_top_assuntos(noticias)
    
    return render_template('dashboard.html', top_assuntos=top_assuntos, data_filtro=data_filtro, assunto_filtro=assunto_filtro, periodo=periodo)