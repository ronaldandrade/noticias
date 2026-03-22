from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from .models import Noticia, Ativo
from .services.sentimento_service import aplicar_scores_em_lote
from .services.cotacao_service import (
    buscar_cotacoes_todos_ativos,
    calcular_correlacao_todos,
)   
from .scraper import buscar_noticias
from . import db
from .repository import filtrar_noticias
import nltk
from nltk import trigrams
from nltk.corpus import stopwords
from collections import Counter
import os

nltk.data.path.append(os.path.join(os.path.dirname(__file__), '../nltk_data'))

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
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

@admin_bp.post("/scoring")
def rodar_scoring():
    """
    Endpoint manual para disparar o pipeline completo:
      1. Atualiza cotações
      2. Calcula scores de sentimento
      3. Calcula correlações
    """
    buscar_cotacoes_todos_ativos(dias=90)
    n_noticias = aplicar_scores_em_lote(limite=1000)
    correlacoes = calcular_correlacao_todos(dias=90)
 
    resultado = []
    for c in correlacoes:
        ativo = Ativo.query.get(c.ativo_id)
        resultado.append({
            "ticker":    ativo.ticker,
            "pearson":   round(c.pearson,   4),
            "spearman":  round(c.spearman,  4),
            "n_noticias": c.n_noticias,
            "periodo":   f"{c.data_inicio} → {c.data_fim}",
        })
 
    return jsonify({
        "noticias_atualizadas": n_noticias,
        "correlacoes": resultado,
    })
 
 
@admin_bp.get("/scores")
def listar_scores():
    """Retorna as últimas 50 notícias com score de sentimento preenchido."""
    noticias = (
        Noticia.query
        .filter(Noticia.score_sentimento.isnot(None))
        .order_by(Noticia.data_publicacao.desc())
        .limit(50)
        .all()
    )
    return jsonify([
        {
            "titulo":    n.titulo,
            "score":     n.score_sentimento,
            "ativo_id":  n.ativo_id,
            "data":      n.data_publicacao.isoformat(),
            "fonte":     n.fonte,
        }
        for n in noticias
    ])

