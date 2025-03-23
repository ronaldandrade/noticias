from flask import Blueprint, render_template, redirect, url_for, request, flash
from .models import Noticia
from .scraper import buscar_noticias
from .repository import filtrar_noticias
from .services.calc_top_new_service import calcular_top_assuntos
import nltk
import os
from rq import Queue
from redis import Redis

nltk.data.path.append(os.path.join(os.path.dirname(__file__), '../nltk_data'))
redis_conn = Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
q = Queue(connection=redis_conn)

bp = Blueprint('main', __name__)

@bp.route('/', methods=['GET'])
def index():
    data_filtro = request.args.get('data', None)
    assunto_filtro = request.args.get('assunto', None)
    periodo = request.args.get('periodo', None)
    page = request.args.get('page', default=1, type=int)
    
    noticias_paginadas = filtrar_noticias(data_filtro, assunto_filtro, periodo, page=page, per_page=10)
    return render_template('index.html', noticias=noticias_paginadas.items, pagination=noticias_paginadas)

@bp.route('/atualizar')
def atualizar():
    q.enqueue(buscar_noticias) 
    flash('Atualizando feed!', 'success')
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
    top_assuntos = calcular_top_assuntos(noticias.items)
    
    return render_template('dashboard.html', top_assuntos=top_assuntos, data_filtro=data_filtro, assunto_filtro=assunto_filtro, periodo=periodo)