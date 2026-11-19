"""
app/cli.py

Comandos Flask para rodar o pipeline pelo terminal.

Uso:
    flask pipeline scraper         # coleta novas notícias
    flask pipeline scoring         # calcula scores de sentimento
    flask pipeline tudo            # scraper + scoring
    flask pipeline status          # mostra contagens do banco
    flask pipeline resetar-scores  # zera scores para recalcular
    flask pipeline categorias      # categoriza notícias sem categoria
"""

import click
from flask.cli import AppGroup

pipeline = AppGroup("pipeline", help="Comandos do pipeline de notícias.")


@pipeline.command("scraper")
def cmd_scraper():
    """Coleta novas notícias de todas as fontes."""
    from app.scraper import buscar_noticias
    click.echo("Coletando notícias...")
    novas = buscar_noticias()
    click.echo(f"Concluído — {len(novas)} notícias novas salvas.")


@pipeline.command("scoring")
@click.option("--limite", default=1000, help="Máximo de notícias para calcular score.")
def cmd_scoring(limite):
    """Calcula scores de sentimento das notícias sem score."""
    from app.services.sentimento_service import aplicar_scores_em_lote
    n = aplicar_scores_em_lote(limite=limite)
    click.echo(f"{n} notícias atualizadas.")


@pipeline.command("tudo")
def cmd_tudo():
    """Roda o pipeline completo: scraper → scoring."""
    from app.scraper import buscar_noticias
    from app.services.sentimento_service import aplicar_scores_em_lote

    click.echo("=== 1. Scraper ===")
    novas = buscar_noticias()
    click.echo(f"   {len(novas)} notícias novas\n")

    click.echo("=== 2. Scores ===")
    n = aplicar_scores_em_lote(limite=1000)
    click.echo(f"   {n} notícias atualizadas\n")

    click.echo("Pipeline concluído.")


@pipeline.command("status")
def cmd_status():
    """Mostra contagens do banco — diagnóstico rápido."""
    from app.models import Noticia

    total = Noticia.query.count()
    com_score = Noticia.query.filter(Noticia.score_sentimento.isnot(None)).count()

    click.echo(f"\n  {'Notícias total':<22} {total}")
    click.echo(f"  {'Com score':<22} {com_score}")
    click.echo(f"  {'Sem score':<22} {total - com_score}\n")


@pipeline.command("resetar-scores")
@click.confirmation_option(prompt="Isso vai zerar todos os scores. Confirma?")
def cmd_resetar():
    """Zera todos os scores para recalcular do zero."""
    from app.services.sentimento_service import resetar_scores
    resetar_scores()
    click.echo("Scores resetados. Rode: flask pipeline scoring")


@pipeline.command("categorias")
@click.option("--limite", default=500)
def cmd_categorias(limite):
    """Categoriza as notícias que ainda não têm categoria."""
    from app.services.ner_service import aplicar_categorias_em_lote
    stats = aplicar_categorias_em_lote(limite=limite)
    click.echo(f"  Processadas: {stats['processadas']}")
    for cat, qtd in sorted(stats["categorias"].items(), key=lambda x: -x[1]):
        click.echo(f"  {cat:<22} {qtd}")
