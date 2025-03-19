from flask import render_template, redirect, url_for, request
from .models import Noticia
from .scraper import buscar_noticias
from .repository import filtrar_noticias, top_assuntos_noticias
from flask import current_app as app
from . import db
import os
import nltk
nltk.data.path.append('/home/ronald/nltk_data')

@app.route('/', methods=['GET'])
def index():
    data_filtro = request.args.get('data', None)
    assunto_filtro = request.args.get('assunto', None)
    periodo = request.args.get('periodo', None)
    noticias = filtrar_noticias(data_filtro, assunto_filtro, periodo, limit=15)
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
    top_assuntos = top_assuntos_noticias(data_filtro, assunto_filtro, periodo)
    return render_template('dashboard.html', top_assuntos=top_assuntos, data_filtro=data_filtro, assunto_filtro=assunto_filtro, periodo=periodo)