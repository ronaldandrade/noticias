import datetime
from flask import render_template, redirect, url_for, request
from .models import Noticia
from .scraper import buscar_noticias
from flask import current_app as app

@app.route('/', methods=['GET'])
def index():
    data_filtro = request.args.get('data')
    assunto_filtro = request.args.get('assunto')

    query = Noticia.query

    if data_filtro:
        try:
            data = datetime.strptime(data_filtro, '%Y-%m-%d')
            query = query.filter(Noticia.data_publicacao >= data)
        except ValueError:
            pass

        if assunto_filtro:
            query = query.filter(
                (Noticia.titulo.ilike(f'%{assunto_filtro}%')) |
                (Noticia.conteudo.ilike(f'%{assunto_filtro}%'))
            )
        
    noticias = Noticia.query.order_by(Noticia.data_publicacao.desc()).all()
    print(f"Notícias carregadas do banco: {len(noticias)}")
    return render_template('index.html', noticias=noticias)

@app.route('/atualizar')
def atualizar():
    buscar_noticias()
    return redirect(url_for('index'))

@app.route("/noticia/<int:id>")
def noticia(id):
    noticia = Noticia.query.get_or_404(id)
    return render_template('noticia.html', noticia=noticia)