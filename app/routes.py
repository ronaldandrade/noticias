from flask import (
    Blueprint, render_template, request, jsonify
)
from .models import Noticia
from .services.sentimento_service import aplicar_scores_em_lote
from .scraper import buscar_noticias
from .decorators import require_cron_secret
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


# ── Rotas principais ───────────────────────────────────────────────────────

CATEGORIAS_LABELS = {
    'mercado_financeiro': 'Mercado Financeiro',
    'política': 'Política',
    'economia_geral': 'Economia Geral',
    'internacional': 'Internacional',
    'tecnologia': 'Tecnologia',
    'energia': 'Energia',
    'agronegócio': 'Agronegócio',
    'saúde': 'Saúde',
    'entretenimento': 'Entretenimento',
    'geral': 'Geral',
}

CATEGORIAS_ICONES = {
    'mercado_financeiro': '📈',
    'política': '🏛',
    'economia_geral': '💹',
    'internacional': '🌐',
    'tecnologia': '💻',
    'energia': '⚡',
    'agronegócio': '🌾',
    'saúde': '🏥',
    'entretenimento': '🎬',
    'geral': '📰',
}


@bp.route('/', methods=['GET'])
def index():
    data_filtro = request.args.get('data', None)
    assunto_filtro = request.args.get('assunto', None)
    periodo = request.args.get('periodo', None)
    categoria_filtro = request.args.get('categoria', None)
    page = request.args.get('page', default=1, type=int)

    noticias_paginadas = filtrar_noticias(
        data_filtro, assunto_filtro, periodo, page=page, per_page=15
    )

    total_noticias = Noticia.query.count()

    scores = db.session.query(Noticia.score_sentimento)\
               .filter(Noticia.score_sentimento.isnot(None)).all()
    scores_list = [r[0] for r in scores]

    total_positivas = sum(1 for s in scores_list if s > 0.05)
    total_negativas = sum(1 for s in scores_list if s < -0.05)
    total_neutras = len(scores_list) - total_positivas - total_negativas
    score_medio = (
        round(sum(scores_list) / len(scores_list), 3) if scores_list else 0.0
    )

    destaques_por_categoria = []
    for slug, label in CATEGORIAS_LABELS.items():
        noticia = (Noticia.query
                   .filter(Noticia.categoria == slug)
                   .order_by(Noticia.data_publicacao.desc())
                   .first())
        if noticia:
            destaques_por_categoria.append({
                'slug': slug,
                'label': label,
                'icone': CATEGORIAS_ICONES.get(slug, '📰'),
                'noticia': noticia,
            })

    return render_template(
        'index.html',
        noticias=noticias_paginadas.items,
        pagination=noticias_paginadas,
        total_noticias=total_noticias,
        total_paginas=noticias_paginadas.pages,
        total_positivas=total_positivas,
        total_negativas=total_negativas,
        total_neutras=total_neutras,
        score_medio=score_medio,
        destaques_por_categoria=destaques_por_categoria,
        categoria_ativa=categoria_filtro or '',
    )


@bp.route('/noticia/<int:id>')
def noticia_detalhe(id):
    noticia = Noticia.query.get_or_404(id)
    return render_template('noticia.html', noticia=noticia)


@bp.route('/dashboard', methods=['GET'])
def dashboard():
    data_filtro = request.args.get('data', None)
    assunto_filtro = request.args.get('assunto', None)
    periodo = request.args.get('periodo', None)

    noticias_paginadas = filtrar_noticias(data_filtro, assunto_filtro, periodo)
    itens = (
        noticias_paginadas.items
        if hasattr(noticias_paginadas, 'items')
        else list(noticias_paginadas)
    )

    titulos = [n.titulo.lower() for n in itens]
    stop_words = set(stopwords.words('portuguese'))
    palavras = []

    for titulo in titulos:
        tokens = nltk.word_tokenize(titulo)
        tokens = [t for t in tokens if t not in stop_words and len(t) > 3]
        trigramas = [' '.join(t) for t in trigrams(tokens)]
        palavras.extend(trigramas)

    contagem = Counter(palavras).most_common(5)
    top_assuntos = [{'assunto': a, 'frequencia': f} for a, f in contagem]

    return render_template(
        'dashboard.html',
        top_assuntos=top_assuntos,
        data_filtro=data_filtro,
        assunto_filtro=assunto_filtro,
        periodo=periodo,
    )


# ── Admin: endpoints operacionais (autenticados por CRON_SECRET) ───────────

@admin_bp.post("/cron/atualizar")
@require_cron_secret
def cron_atualizar():
    buscar_noticias()
    n = aplicar_scores_em_lote(limite=500)

    return jsonify({"status": "ok", "scores_atualizados": n})


@admin_bp.get("/scores")
@require_cron_secret
def listar_scores():
    noticias = (
        Noticia.query
        .filter(Noticia.score_sentimento.isnot(None))
        .order_by(Noticia.data_publicacao.desc())
        .limit(50)
        .all()
    )
    return jsonify([
        {
            "titulo": n.titulo,
            "score": n.score_sentimento,
            "data": n.data_publicacao.isoformat(),
        }
        for n in noticias
    ])


@admin_bp.get("/status")
@require_cron_secret
def status():
    return jsonify({
        "noticias": Noticia.query.count(),
        "com_score": Noticia.query.filter(
            Noticia.score_sentimento.isnot(None)
        ).count(),
        "sem_score": Noticia.query.filter(
            Noticia.score_sentimento.is_(None)
        ).count(),
    })
