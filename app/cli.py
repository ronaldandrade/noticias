"""
app/cli.py

Comandos Flask para rodar o pipeline pelo terminal.

Uso:
    flask pipeline scraper              # coleta novas notícias
    flask pipeline scoring              # calcula scores e correlações
    flask pipeline reatribuir           # reatribui notícias aos ativos
    flask pipeline tudo                 # roda tudo em sequência
    flask pipeline status               # mostra contagens do banco
    flask pipeline cotacoes --dias **   # baixa cotações dos últimos (qtd dias) dias para todos os ativos
    flask pipeline resetar-scores       # zera scores para recalcular
"""

import click
from flask.cli import AppGroup

pipeline = AppGroup("pipeline", help="Comandos do pipeline de notícias financeiras.")


@pipeline.command("scraper")
def cmd_scraper():
    """Coleta novas notícias de todas as fontes."""
    from app.scraper import buscar_noticias
    click.echo("Coletando notícias...")
    novas = buscar_noticias()
    click.echo(f"Concluído — {len(novas)} notícias novas salvas.")


@pipeline.command("scoring")
@click.option("--dias", default=90, help="Janela de dias para cotações e correlações.")
@click.option("--limite", default=1000, help="Máximo de notícias para calcular score.")
def cmd_scoring(dias, limite):
    """Atualiza cotações, calcula scores de sentimento e correlações."""
    from app.services.cotacao_service import buscar_cotacoes_todos_ativos, calcular_correlacao_todos
    from app.services.sentimento_service import aplicar_scores_em_lote
    from app.models import Ativo

    click.echo("1. Buscando cotações...")
    buscar_cotacoes_todos_ativos(dias=dias)

    click.echo("2. Calculando scores de sentimento...")
    n = aplicar_scores_em_lote(limite=limite)
    click.echo(f"   {n} notícias atualizadas.")

    click.echo("3. Calculando correlações...")
    resultados = calcular_correlacao_todos(dias=dias)
    for c in resultados:
        ativo = Ativo.query.get(c.ativo_id)
        ticker = ativo.ticker if ativo else f"id={c.ativo_id}"
        click.echo(
            f"   {ticker:<14} "
            f"pearson={c.pearson:+.3f}  "
            f"spearman={c.spearman:+.3f}  "
            f"({c.n_noticias} notícias)"
        )

    click.echo("Concluído.")


@pipeline.command("reatribuir")
def cmd_reatribuir():
    """Reatribui ativo_id de todas as notícias com o algoritmo de pontuação."""
    from app.models import Noticia, Ativo
    from app.services.assossiacao_service import associar_ativo
    from app import db

    ativos   = Ativo.query.all()
    noticias = Noticia.query.all()
    total    = len(noticias)

    click.echo(f"Reatribuindo {total} notícias...")

    contagem    = {a.ticker: 0 for a in ativos}
    sem_ativo   = 0
    atualizadas = 0

    for i, noticia in enumerate(noticias):
        novo_id = associar_ativo(noticia.titulo, noticia.conteudo or "", ativos)

        if noticia.ativo_id != novo_id:
            noticia.ativo_id = novo_id
            atualizadas += 1

        if novo_id:
            ativo = next((a for a in ativos if a.id == novo_id), None)
            if ativo:
                contagem[ativo.ticker] += 1
        else:
            sem_ativo += 1

        if i % 200 == 0 and i > 0:
            db.session.commit()
            click.echo(f"  {i}/{total} processadas...")

    db.session.commit()

    click.echo(f"\nConcluído — {atualizadas} notícias atualizadas\n")
    click.echo(f"  {'Ativo':<14} {'Notícias':>8}")
    click.echo(f"  {'─'*14} {'─'*8}")
    for ticker, qtd in sorted(contagem.items(), key=lambda x: -x[1]):
        if qtd > 0:
            click.echo(f"  {ticker:<14} {qtd:>8}")
    click.echo(f"  {'sem ativo':<14} {sem_ativo:>8}")


@pipeline.command("tudo")
@click.option("--dias", default=90, help="Janela de dias para cotações e correlações.")
def cmd_tudo(dias):
    """Roda o pipeline completo: scraper → scoring → correlações."""
    from app.scraper import buscar_noticias
    from app.services.cotacao_service import buscar_cotacoes_todos_ativos, calcular_correlacao_todos
    from app.services.sentimento_service import aplicar_scores_em_lote
    from app.models import Ativo

    click.echo("=== 1. Scraper ===")
    novas = buscar_noticias()
    click.echo(f"   {len(novas)} notícias novas\n")

    click.echo("=== 2. Cotações ===")
    buscar_cotacoes_todos_ativos(dias=dias)
    click.echo("   Cotações atualizadas\n")

    click.echo("=== 3. Scores ===")
    n = aplicar_scores_em_lote(limite=1000)
    click.echo(f"   {n} notícias atualizadas\n")

    click.echo("=== 4. Correlações ===")
    resultados = calcular_correlacao_todos(dias=dias)
    for c in resultados:
        ativo = Ativo.query.get(c.ativo_id)
        ticker = ativo.ticker if ativo else f"id={c.ativo_id}"
        click.echo(f"   {ticker:<14} pearson={c.pearson:+.3f}  spearman={c.spearman:+.3f}")

    click.echo("\nPipeline concluído.")


@pipeline.command("status")
def cmd_status():
    """Mostra contagens do banco — diagnóstico rápido."""
    from app.models import Noticia, Ativo, Cotacao, Correlacao

    total     = Noticia.query.count()
    com_score = Noticia.query.filter(Noticia.score_sentimento.isnot(None)).count()
    sem_score = Noticia.query.filter(Noticia.score_sentimento.is_(None)).count()

    click.echo(f"\n  {'Notícias total':<22} {total}")
    click.echo(f"  {'Com score':<22} {com_score}")
    click.echo(f"  {'Sem score':<22} {sem_score}")
    click.echo(f"  {'Ativos':<22} {Ativo.query.count()}")
    click.echo(f"  {'Cotações':<22} {Cotacao.query.count()}")
    click.echo(f"  {'Correlações':<22} {Correlacao.query.count()}\n")

    ativos = Ativo.query.all()
    click.echo(f"  {'Ativo':<14} {'Notícias':>9} {'Com score':>10}")
    click.echo(f"  {'─'*14} {'─'*9} {'─'*10}")
    for ativo in ativos:
        n_total = Noticia.query.filter_by(ativo_id=ativo.id).count()
        n_score = Noticia.query.filter(
            Noticia.ativo_id == ativo.id,
            Noticia.score_sentimento.isnot(None)
        ).count()
        if n_total > 0:
            click.echo(f"  {ativo.ticker:<14} {n_total:>9} {n_score:>10}")

@pipeline.command("cotacoes")
@click.option("--dias", default=90, help="Número de dias para retroagir.")
def cmd_cotacoes(dias):
    """Baixa cotações históricas para todos os ativos cadastrados."""
    from .services.cotacao_service import buscar_cotacoes_todos_ativos
    click.echo(f"Atualizando cotações (últimos {dias} dias)...")
    buscar_cotacoes_todos_ativos(dias=dias)
    click.echo("Cotações atualizadas com sucesso.")

@pipeline.command("resetar-scores")
@click.confirmation_option(prompt="Isso vai zerar todos os scores. Confirma?")
def cmd_resetar():
    """Zera todos os scores e ativo_id para recalcular do zero."""
    from app.services.sentimento_service import resetar_scores
    resetar_scores()
    click.echo("Scores resetados. Rode: flask pipeline scoring")

@pipeline.command("ner")
@click.option("--limite", default=500)
def cmd_ner(limite):
    # \"\"\"Aplica NER e categorização nas notícias sem ativo ou sem categoria.\"\"\"
    from app.services.ner_service import aplicar_ner_em_lote
    click.echo("Rodando NER...")
    stats = aplicar_ner_em_lote(limite=limite)
    click.echo(f"  Processadas:       {stats['processadas']}")
    click.echo(f"  Ativos encontrados: {stats['ativo_encontrado']}")
    click.echo("\\n  Categorias:")
    for cat, qtd in sorted(stats["categorias"].items(), key=lambda x: -x[1]):
        click.echo(f"  {cat:<22} {qtd}")