"""
Como usar o serviço de sentimento — duas formas:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 FORMA 1 — Terminal (script avulso)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  python run_scoring.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 FORMA 2 — Rota Flask  POST /admin/scoring
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  curl -X POST http://localhost:5000/admin/scoring

Adicione o blueprint ao seu create_app():
    from app.routes.admin import admin_bp
    app.register_blueprint(admin_bp)
"""

# ════════════════════════════════════════════════
# run_scoring.py  (coloque na raiz do projeto)
# ════════════════════════════════════════════════
RUN_SCORING = '''
from app import create_app
from app.services.sentimento_service import aplicar_scores_em_lote
from app.services.cotacao_service import (
    buscar_cotacoes_todos_ativos,
    calcular_correlacao_todos,
)

app = create_app()

with app.app_context():
    print("=== 1. Buscando cotações ===")
    buscar_cotacoes_todos_ativos(dias=90)

    print("\\n=== 2. Calculando scores de sentimento ===")
    n = aplicar_scores_em_lote(limite=1000)
    print(f"   {n} notícias atualizadas")

    print("\\n=== 3. Calculando correlações ===")
    resultados = calcular_correlacao_todos(dias=90)
    for c in resultados:
        from app.models import Ativo
        ativo = Ativo.query.get(c.ativo_id)
        print(
            f"   {ativo.ticker:<12} "
            f"pearson={c.pearson:+.3f}  "
            f"spearman={c.spearman:+.3f}  "
            f"({c.n_noticias} notícias)"
        )

    print("\\nConcluído.")
'''

# ════════════════════════════════════════════════
# routes/admin.py  (blueprint Flask)
# ════════════════════════════════════════════════
ADMIN_BLUEPRINT = '''
from flask import Blueprint, jsonify
from ..services.sentimento_service import aplicar_scores_em_lote
from ..services.cotacao_service import (
    buscar_cotacoes_todos_ativos,
    calcular_correlacao_todos,
)
from ..models import Ativo

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


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
    from ..models import Noticia
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
'''

if __name__ == "__main__":
    print("=== run_scoring.py ===")
    print(RUN_SCORING)
    print("\n\n=== routes/admin.py ===")
    print(ADMIN_BLUEPRINT)