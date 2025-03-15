# app/routes.py
from flask import render_template, redirect, url_for, request
from .models import Noticia
from .scraper import buscar_noticias
from flask import current_app as app
from datetime import datetime

@app.route('/', methods=['GET'])
def index():
    data_filtro = request.args.get('data', None)
    assunto_filtro = request.args.get('assunto', None)
    
    print(f"Data filtro recebida: {data_filtro}")
    print(f"Assunto filtro recebido: {assunto_filtro}")
    
    query = Noticia.query
    
    if data_filtro:
        try:
            data = datetime.strptime(data_filtro, '%Y-%m-%d')
            print(f"Data convertida: {data}")
            query = query.filter(Noticia.data_publicacao >= data)
        except ValueError as e:
            print(f"Erro ao converter data: {e}")
    
    if assunto_filtro:
        query = query.filter(
            (Noticia.titulo.ilike(f'%{assunto_filtro}%')) |
            (Noticia.conteudo.ilike(f'%{assunto_filtro}%'))
        )
        print(f"Filtrando por assunto: {assunto_filtro}")
    
    noticias = query.order_by(Noticia.data_publicacao.desc()).all()
    print(f"Notícias carregadas do banco: {len(noticias)}")
    for n in noticias[:5]:
        print(f"Notícia: {n.titulo} - {n.data_publicacao}")
    
    return render_template('index.html', noticias=noticias)

@app.route('/atualizar')
def atualizar():
    buscar_noticias()
    return redirect(url_for('index'))

@app.route('/noticia/<int:id>')
def noticia_detalhe(id):
    noticia = Noticia.query.get_or_404(id)
    return render_template('noticia.html', noticia=noticia)