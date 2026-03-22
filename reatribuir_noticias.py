"""
reatribuir_noticias.py

Reatribui ativo_id de todas as notícias usando o algoritmo novo de pontuação.
Rode uma vez após instalar o associacao_service.py.

    python reatribuir_noticias.py
"""

from app import create_app, db
from app.models import Noticia, Ativo
from app.services.assosciacao_service import associar_ativo

app = create_app()

with app.app_context():
    ativos   = Ativo.query.all()
    noticias = Noticia.query.all()
    total    = len(noticias)

    print(f"Reatribuindo {total} notícias...\n")

    contagem = {a.ticker: 0 for a in ativos}
    sem_ativo = 0
    atualizadas = 0

    for i, noticia in enumerate(noticias):
        novo_id = associar_ativo(
            noticia.titulo,
            noticia.conteudo or "",
            ativos,
        )

        if noticia.ativo_id != novo_id:
            noticia.ativo_id = novo_id
            atualizadas += 1

        if novo_id:
            ativo = next((a for a in ativos if a.id == novo_id), None)
            if ativo:
                contagem[ativo.ticker] += 1
        else:
            sem_ativo += 1

        # Commit parcial a cada 200
        if i % 200 == 0 and i > 0:
            db.session.commit()
            print(f"  {i}/{total} processadas...")

    db.session.commit()

    print(f"\nConcluído — {atualizadas} notícias atualizadas\n")
    print(f"  {'Ativo':<14} {'Notícias':>8}")
    print(f"  {'─'*14} {'─'*8}")
    for ticker, qtd in sorted(contagem.items(), key=lambda x: -x[1]):
        if qtd > 0:
            print(f"  {ticker:<14} {qtd:>8}")
    print(f"  {'sem ativo':<14} {sem_ativo:>8}")
    print()
    print("Rode agora: python run_scoring.py  (para recalcular correlações)")