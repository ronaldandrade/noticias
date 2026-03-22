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

    print("\n=== 2. Calculando scores de sentimento ===")
    n = aplicar_scores_em_lote(limite=1000)
    print(f"   {n} notícias atualizadas")

    print("\n=== 3. Calculando correlações ===")
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

    print("\nConcluído.")