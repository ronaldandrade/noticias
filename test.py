"""
test.py — Diagnóstico completo do pipeline de notícias financeiras

Rode com:
    python test.py

Verifica cada camada e mostra o que está funcionando e o que precisa de ajuste.
"""

import sys

# ── Setup da aplicação ────────────────────────────────────────────────────────
from app import create_app, db
from app.models import Noticia, Ativo, Cotacao, Correlacao

app = create_app()

# Cores no terminal
OK   = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m!\033[0m"
INFO = "\033[94m→\033[0m"
SEP  = "─" * 60


def titulo(texto):
    print(f"\n{SEP}")
    print(f"  {texto}")
    print(SEP)


def ok(msg):   print(f"  {OK}  {msg}")
def fail(msg): print(f"  {FAIL}  {msg}")
def warn(msg): print(f"  {WARN}  {msg}")
def info(msg): print(f"  {INFO}  {msg}")


# ══════════════════════════════════════════════════════════════════════════════
with app.app_context():

    erros = 0

    # ── 1. Banco de dados ─────────────────────────────────────────────────────
    titulo("1. BANCO DE DADOS")

    total_noticias   = Noticia.query.count()
    total_ativos     = Ativo.query.count()
    total_cotacoes   = Cotacao.query.count()
    total_correlacao = Correlacao.query.count()

    ok(f"Notícias:    {total_noticias}")
    ok(f"Ativos:      {total_ativos}")
    ok(f"Cotações:    {total_cotacoes}")
    ok(f"Correlações: {total_correlacao}")

    if total_noticias == 0:
        fail("Nenhuma notícia no banco — rode o scraper primeiro")
        erros += 1
    if total_ativos == 0:
        fail("Nenhum ativo cadastrado — rode seed_ativos()")
        erros += 1
    if total_cotacoes == 0:
        warn("Nenhuma cotação — rode buscar_cotacoes_todos_ativos()")

    # ── 2. Scores de sentimento ───────────────────────────────────────────────
    titulo("2. SCORES DE SENTIMENTO")

    com_score    = Noticia.query.filter(Noticia.score_sentimento.isnot(None)).count()
    sem_score    = Noticia.query.filter(Noticia.score_sentimento.is_(None)).count()
    com_ativo    = Noticia.query.filter(Noticia.ativo_id.isnot(None)).count()

    if com_score > 0:
        ok(f"Com score:    {com_score} notícias")
    else:
        fail("Nenhuma notícia com score — rode aplicar_scores_em_lote()")
        erros += 1

    if sem_score > 0:
        warn(f"Sem score:    {sem_score} notícias (rodar aplicar_scores_em_lote)")

    if com_ativo > 0:
        ok(f"Associadas a um ativo: {com_ativo} notícias")
    else:
        warn("Nenhuma notícia associada a um ativo (veja seção 4)")

    # Amostra de scores
    if com_score > 0:
        amostras = (
            Noticia.query
            .filter(Noticia.score_sentimento.isnot(None))
            .order_by(Noticia.data_publicacao.desc())
            .limit(5)
            .all()
        )
        print()
        print("  Últimas 5 notícias com score:")
        print(f"  {'Score':>7}  Título")
        print(f"  {'─'*7}  {'─'*45}")
        for n in amostras:
            sinal = "+" if n.score_sentimento >= 0 else ""
            print(f"  {sinal}{n.score_sentimento:>6.3f}  {n.titulo[:55]}")

    # ── 3. Ativos e cotações ──────────────────────────────────────────────────
    titulo("3. ATIVOS E COTAÇÕES")

    ativos = Ativo.query.all()
    for ativo in ativos:
        n_cot = Cotacao.query.filter_by(ativo_id=ativo.id).count()
        ultima = (
            Cotacao.query
            .filter_by(ativo_id=ativo.id)
            .order_by(Cotacao.data.desc())
            .first()
        )
        if n_cot > 0:
            ok(f"{ativo.ticker:<12} {n_cot:>4} cotações  última: {ultima.data}  "
               f"fechamento: R${ultima.preco_fechamento:.2f}")
        else:
            warn(f"{ativo.ticker:<12} sem cotações")

    # ── 4. Associação notícias → ativos ───────────────────────────────────────
    titulo("4. ASSOCIAÇÃO NOTÍCIAS → ATIVOS")

    print("  Notícias por ativo:")
    for ativo in ativos:
        n = Noticia.query.filter_by(ativo_id=ativo.id).count()
        if n > 0:
            ok(f"{ativo.ticker:<12} {n} notícias associadas")
        else:
            warn(f"{ativo.ticker:<12} 0 notícias — ticker não aparece nas notícias coletadas")

    # Diagnóstico: mostra os 10 títulos mais recentes para inspeção manual
    print()
    print("  10 títulos mais recentes no banco (para inspeção):")
    recentes = (
        Noticia.query
        .order_by(Noticia.data_publicacao.desc())
        .limit(10)
        .all()
    )
    for n in recentes:
        ativo_label = f"[ativo_id={n.ativo_id}]" if n.ativo_id else "[sem ativo]"
        print(f"  {ativo_label:<16} {n.titulo[:55]}")

    # ── 5. Teste de sentimento ao vivo ────────────────────────────────────────
    titulo("5. TESTE DE SENTIMENTO AO VIVO")

    from app.services.sentimento_service import calcular_score

    casos = [
        ("Petrobras registra lucro recorde no trimestre",         "positivo"),
        ("Vale sofre queda após acidente em barragem",            "negativo"),
        ("Ibovespa fecha estável em sessão de baixo volume",      "neutro"),
        ("Bradesco bate estimativas e sobe 3% na bolsa",          "positivo"),
        ("Inflação acelera e preocupa mercado financeiro",        "negativo"),
        ("Bitcoin atinge nova máxima histórica",                  "positivo"),
        ("Magazine Luiza reporta prejuízo e ações despencam",     "negativo"),
    ]

    print(f"  {'Score':>7}  {'Esperado':<10}  Texto")
    print(f"  {'─'*7}  {'─'*10}  {'─'*42}")

    acertos = 0
    for texto, esperado in casos:
        score = calcular_score(texto)
        sinal = "+" if score >= 0 else ""

        if esperado == "positivo" and score > 0.05:
            resultado = OK
            acertos += 1
        elif esperado == "negativo" and score < -0.05:
            resultado = OK
            acertos += 1
        elif esperado == "neutro" and -0.1 <= score <= 0.1:
            resultado = OK
            acertos += 1
        else:
            resultado = FAIL
            erros += 1

        print(f"  {sinal}{score:>6.3f}  {resultado} {esperado:<8}  {texto[:42]}")

    print(f"\n  Acertos: {acertos}/{len(casos)}")

    # ── 6. Correlações calculadas ─────────────────────────────────────────────
    titulo("6. CORRELAÇÕES CALCULADAS")

    correlacoes = Correlacao.query.order_by(Correlacao.criado_em.desc()).all()
    if correlacoes:
        print(f"  {'Ticker':<12} {'Pearson':>8} {'Spearman':>9} {'Notícias':>9}  Período")
        print(f"  {'─'*12} {'─'*8} {'─'*9} {'─'*9}  {'─'*22}")
        for c in correlacoes:
            ativo = Ativo.query.get(c.ativo_id)
            ticker = ativo.ticker if ativo else f"id={c.ativo_id}"
            print(
                f"  {ticker:<12} {c.pearson:>+8.3f} {c.spearman:>+9.3f} "
                f"{c.n_noticias:>9}  {c.data_inicio} → {c.data_fim}"
            )
    else:
        warn("Nenhuma correlação calculada ainda")
        info("Isso é esperado se não há notícias associadas a ativos")

    # ── Resumo final ──────────────────────────────────────────────────────────
    titulo("RESUMO")

    if erros == 0:
        print(f"  {OK}  Pipeline funcionando corretamente!\n")
    else:
        print(f"  {FAIL}  {erros} problema(s) encontrado(s) — veja os itens acima\n")

    # ── 7. Sugestão de fontes por ativo ───────────────────────────────────────
    titulo("7. SUGESTÃO — TERMOS PARA BUSCA NAS FONTES RSS")

    print("  Se nenhum ativo está sendo associado às notícias, considere")
    print("  adicionar feeds RSS específicos por empresa:\n")

    sugestoes = {
        "PETR4.SA":  ["Petrobras", "petróleo", "pré-sal", "PETR4"],
        "VALE3.SA":  ["Vale", "minério de ferro", "VALE3"],
        "ITUB4.SA":  ["Itaú", "Itaú Unibanco", "ITUB4"],
        "BBDC4.SA":  ["Bradesco", "BBDC4"],
        "MGLU3.SA":  ["Magazine Luiza", "Magalu", "MGLU3"],
        "BTC-USD":   ["Bitcoin", "BTC", "criptomoeda", "cripto"],
        "^BVSP":     ["Ibovespa", "Bovespa", "bolsa", "B3"],
    }

    for ticker, termos in sugestoes.items():
        print(f"  {ticker:<12} → palavras-chave: {', '.join(termos)}")

    print()
    print("  Fontes RSS recomendadas por ativo:")
    print("  InfoMoney por tag:  https://www.infomoney.com.br/ferramentas/rss/")
    print("  Valor por empresa:  https://valor.globo.com/empresas/")
    print()