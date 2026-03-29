from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash
from .models import Noticia, Ativo
from .services.sentimento_service import aplicar_scores_em_lote
from .services.cotacao_service import (
    buscar_cotacoes_todos_ativos,
    calcular_correlacao_todos,
)
from .services.relatorio_service import gerar_dados_relatorio
from .services.termometro_service import gerar_termometro
from .services.ner_service import aplicar_ner_em_lote
from .scraper import buscar_noticias
from . import db
from .repository import filtrar_noticias
import nltk
from nltk import trigrams
from nltk.corpus import stopwords
from collections import Counter
import os


nltk.data.path.append(os.path.join(os.path.dirname(__file__), '../nltk_data'))

admin_bp    = Blueprint("admin",    __name__, url_prefix="/admin")
bp          = Blueprint('main',     __name__)
relatorio_bp = Blueprint("relatorio", __name__, url_prefix="/relatorio")
termometro_bp = Blueprint("termometro", __name__, url_prefix="/termometro")


# ── Rotas principais ──────────────────────────────────────────────────────────

@bp.route('/', methods=['GET'])
def index():
 
    data_filtro    = request.args.get('data',    None)
    assunto_filtro = request.args.get('assunto', None)
    periodo        = request.args.get('periodo', None)
    categoria_filtro = request.args.get('categoria', None)
    page           = request.args.get('page', default=1, type=int)
 
    noticias_paginadas = filtrar_noticias(
        data_filtro, assunto_filtro, periodo, page=page, per_page=15
    )
 
    # Pré-carrega relação ativo para evitar N+1 queries no template
    from sqlalchemy.orm import joinedload
    ids_pagina = [n.id for n in noticias_paginadas.items]
 
    # ── Visão geral (sobre todo o banco, não só a página atual) ──────────────
    total_noticias  = Noticia.query.count()
    total_paginas   = noticias_paginadas.pages
 
    scores = db.session.query(Noticia.score_sentimento)\
               .filter(Noticia.score_sentimento.isnot(None)).all()
    scores_list = [r[0] for r in scores]
 
    total_positivas = sum(1 for s in scores_list if s >  0.05)
    total_negativas = sum(1 for s in scores_list if s < -0.05)
    total_neutras   = len(scores_list) - total_positivas - total_negativas
    score_medio     = round(sum(scores_list) / len(scores_list), 3) if scores_list else 0.0
    total_com_ativo = Noticia.query.filter(Noticia.ativo_id.isnot(None)).count()
 
    # Adiciona relação ativo em cada notícia da página para o template
    ativos_map = {a.id: a for a in Ativo.query.all()}
    for n in noticias_paginadas.items:
        n.ativo = ativos_map.get(n.ativo_id)
 
    return render_template(
        'index.html',
        noticias=noticias_paginadas.items,
        pagination=noticias_paginadas,
        total_noticias=total_noticias,
        total_paginas=total_paginas,
        total_positivas=total_positivas,
        total_negativas=total_negativas,
        total_neutras=total_neutras,
        score_medio=score_medio,
        total_com_ativo=total_com_ativo,
    )
@bp.route('/atualizar')
def atualizar():
    import threading
    from flask import current_app

    app = current_app._get_current_object()

    def rodar_em_background():
        with app.app_context():
            try:
                buscar_noticias()
                buscar_cotacoes_todos_ativos(dias=1)
                aplicar_scores_em_lote(limite=200)
                aplicar_ner_em_lote(limite=200)
                app.logger.info("Pipeline concluído com sucesso.")
            except Exception as e:
                app.logger.error(f"Erro no pipeline: {e}")

    thread = threading.Thread(target=rodar_em_background, daemon=True)
    thread.start()
    return redirect(url_for('main.index'))

@bp.route('/noticia/<int:id>')
def noticia_detalhe(id):
    noticia = Noticia.query.get_or_404(id)
    return render_template('noticia.html', noticia=noticia)


@bp.route('/dashboard', methods=['GET'])
def dashboard():
    data_filtro    = request.args.get('data',    None)
    assunto_filtro = request.args.get('assunto', None)
    periodo        = request.args.get('periodo', None)

    noticias_paginadas = filtrar_noticias(data_filtro, assunto_filtro, periodo)

    # Garante que temos uma lista mesmo que o resultado venha paginado
    itens = noticias_paginadas.items if hasattr(noticias_paginadas, 'items') else list(noticias_paginadas)

    titulos    = [n.titulo.lower() for n in itens]
    stop_words = set(stopwords.words('portuguese'))
    palavras   = []

    for titulo in titulos:
        tokens    = nltk.word_tokenize(titulo)
        tokens    = [t for t in tokens if t not in stop_words and len(t) > 3]
        trigramas = [' '.join(t) for t in trigrams(tokens)]
        palavras.extend(trigramas)

    contagem    = Counter(palavras).most_common(5)
    top_assuntos = [{'assunto': a, 'frequencia': f} for a, f in contagem]

    # Passa scores por ativo para o dashboard poder exibir
    ativos = Ativo.query.all()
    scores_por_ativo = []
    for ativo in ativos:
        noticias_ativo = [n for n in itens if n.ativo_id == ativo.id and n.score_sentimento is not None]
        if noticias_ativo:
            media = sum(n.score_sentimento for n in noticias_ativo) / len(noticias_ativo)
            scores_por_ativo.append({
                'ticker': ativo.ticker.replace('.SA', ''),
                'nome':   ativo.nome,
                'score':  round(media, 3),
                'total':  len(noticias_ativo),
            })

    return render_template(
        'dashboard.html',
        top_assuntos=top_assuntos,
        scores_por_ativo=scores_por_ativo,
        data_filtro=data_filtro,
        assunto_filtro=assunto_filtro,
        periodo=periodo,
    )

@admin_bp.post("/cron/atualizar")
def cron_atualizar():
    """Chamado pelo GitHub Actions automaticamente."""
    secret = request.headers.get("X-Cron-Secret", "")
    if secret != os.environ.get("CRON_SECRET", ""):
        return jsonify({"erro": "não autorizado"}), 401

    buscar_noticias()
    buscar_cotacoes_todos_ativos(dias=1)
    n = aplicar_scores_em_lote(limite=500)
    calcular_correlacao_todos(dias=90)

    return jsonify({"status": "ok", "scores_atualizados": n})


# ── Relatório ─────────────────────────────────────────────────────────────────

@relatorio_bp.get("/")
def relatorio():
    dias  = int(request.args.get("dias", 90))
    dados = gerar_dados_relatorio(dias=dias)
    return render_template("relatorio.html", **dados)

# ── Termômetro ─────────────────────────────────────────────────────────────────

@termometro_bp.get("/")
def termometro():
    dados = gerar_termometro()
    return render_template("termometro.html", **dados)

# ── Admin / API ───────────────────────────────────────────────────────────────

@admin_bp.post("/scoring")
def rodar_scoring():
    """
    Pipeline completo via POST:
      1. Busca cotações
      2. Aplica scores nas notícias ainda sem score
      3. Recalcula correlações
    """
    buscar_cotacoes_todos_ativos(dias=90)
    n_noticias  = aplicar_scores_em_lote(limite=1000)
    correlacoes = calcular_correlacao_todos(dias=90)

    resultado = []
    for c in correlacoes:
        ativo = Ativo.query.get(c.ativo_id)
        if not ativo:
            continue
        resultado.append({
            "ticker":     ativo.ticker,
            "pearson":    round(c.pearson,  4) if c.pearson  is not None else None,
            "spearman":   round(c.spearman, 4) if c.spearman is not None else None,
            "n_noticias": c.n_noticias,
            "periodo":    f"{c.data_inicio} → {c.data_fim}",
        })

    return jsonify({
        "noticias_atualizadas": n_noticias,
        "correlacoes": resultado,
    })


@admin_bp.post("/atualizar-completo")
def atualizar_completo():
    """
    Versão completa do /atualizar:
    raspa notícias + cotações + correlações em uma chamada só.
    Útil para chamar via cron ou APScheduler.
    """
    buscar_noticias()
    buscar_cotacoes_todos_ativos(dias=90)
    n_noticias  = aplicar_scores_em_lote(limite=500)
    correlacoes = calcular_correlacao_todos(dias=90)

    return jsonify({
        "status": "ok",
        "noticias_atualizadas": n_noticias,
        "correlacoes_calculadas": len(correlacoes),
    })


@admin_bp.get("/scores")
def listar_scores():
    """Últimas 50 notícias com score — útil para debug."""
    noticias = (
        Noticia.query
        .filter(Noticia.score_sentimento.isnot(None))
        .order_by(Noticia.data_publicacao.desc())
        .limit(50)
        .all()
    )
    return jsonify([
        {
            "titulo":   n.titulo,
            "score":    n.score_sentimento,
            "ativo_id": n.ativo_id,
            "data":     n.data_publicacao.isoformat(),
        }
        for n in noticias
    ])


@admin_bp.get("/status")
def status():
    """Health check rápido do pipeline — retorna contagens do banco."""
    from .models import Cotacao, Correlacao

    return jsonify({
        "noticias":        Noticia.query.count(),
        "com_score":       Noticia.query.filter(Noticia.score_sentimento.isnot(None)).count(),
        "sem_score":       Noticia.query.filter(Noticia.score_sentimento.is_(None)).count(),
        "cotacoes":        Cotacao.query.count(),
        "correlacoes":     Correlacao.query.count(),
        "ativos":          Ativo.query.count(),
    })
