from flask import render_template, redirect, url_for
from .models import Noticia
from .scraper import buscar_noticias
from flask import current_app as app

@app.route('/')
def index():
    noticias = Noticia.query.order_by(Noticia.data_publicacao.desc()).all()
    print(f"Notícias carregadas do banco: {len(noticias)}")
    return render_template('index.html', noticias=noticias)

@app.route('/atualizar')
def atualizar():
    buscar_noticias()
    return redirect(url_for('index'))