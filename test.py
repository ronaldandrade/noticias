"""
test.py — Diagnóstico do pipeline de notícias (coleta + sentimento)

Rode com:
    python test.py
"""

from app import create_app, db
from app.models import Noticia

app = create_app()

OK, FAIL = "\033[92m✓\033[0m", "\033[91m✗\033[0m"
SEP = "─" * 60


def titulo(texto):
    print(f"\n{SEP}\n  {texto}\n{SEP}")


with app.app_context():
    titulo("1. BANCO DE DADOS")
    total = Noticia.query.count()
    print(f"  {OK if total else FAIL}  Notícias: {total}")

    titulo("2. SCORES DE SENTIMENTO")
    com_score = Noticia.query.filter(Noticia.score_sentimento.isnot(None)).count()
    print(f"  {OK if com_score == total else FAIL}  Com score: {com_score}/{total}")
    print("\n  Últimas 5 notícias:")
    for n in Noticia.query.order_by(Noticia.data_publicacao.desc()).limit(5):
        s = n.score_sentimento
        print(f"  {'—' if s is None else f'{s:+.3f}'}  {n.titulo[:60]}")

    titulo("3. CATEGORIAS")
    rows = (db.session.query(Noticia.categoria, db.func.count(Noticia.id))
            .group_by(Noticia.categoria).order_by(db.func.count(Noticia.id).desc()).all())
    for cat, qtd in rows:
        print(f"  {str(cat):<22} {qtd}")

    titulo("4. TESTE DE SENTIMENTO AO VIVO")
    from app.services.sentimento_service import calcular_score
    casos = [
        ("Petrobras registra lucro recorde no trimestre", 1),
        ("Vale sofre queda após acidente em barragem", -1),
        ("Ibovespa fecha estável em sessão de baixo volume", 0),
        ("Bradesco bate estimativas e sobe 3% na bolsa", 1),
        ("Inflação acelera e preocupa mercado financeiro", -1),
        ("Magazine Luiza reporta prejuízo e ações despencam", -1),
    ]
    acertos = 0
    for texto, esperado in casos:
        sc = calcular_score(texto)
        ok = (sc > 0.05) if esperado > 0 else (sc < -0.05) if esperado < 0 else abs(sc) <= 0.05
        acertos += ok
        print(f"  {sc:+.3f}  {OK if ok else FAIL}  {texto}")
    print(f"\n  Acertos: {acertos}/{len(casos)}")
