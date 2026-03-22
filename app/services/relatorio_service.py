"""
services/relatorio_service.py

Prepara todos os dados necessários para o template do relatório:
  - Resumo geral (contagens, scores médios)
  - Série temporal sentimento × preço por ativo
  - Heatmap sentimento por dia da semana × ativo
  - Tabela de correlações
  - Últimas notícias com score
"""

from datetime import date, timedelta
from collections import defaultdict

import json

from ..models import Noticia, Ativo, Cotacao, Correlacao
from .. import db


def _json(obj) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False)


def gerar_dados_relatorio(dias: int = 90) -> dict:
    data_inicio = date.today() - timedelta(days=dias)
    ativos      = Ativo.query.all()
    ativo_map   = {a.id: a for a in ativos}

    # ── 1. Cards de resumo ────────────────────────────────────────────────────
    total_noticias = Noticia.query.count()
    com_score      = Noticia.query.filter(Noticia.score_sentimento.isnot(None)).count()

    scores_raw = (
        db.session.query(Noticia.score_sentimento)
        .filter(Noticia.score_sentimento.isnot(None))
        .all()
    )
    scores_list = [r[0] for r in scores_raw]
    score_medio = round(sum(scores_list) / len(scores_list), 3) if scores_list else 0.0

    positivas = sum(1 for s in scores_list if s > 0.05)
    negativas = sum(1 for s in scores_list if s < -0.05)
    neutras   = len(scores_list) - positivas - negativas

    resumo = {
        "total_noticias":  total_noticias,
        "com_score":       com_score,
        "score_medio":     score_medio,
        "positivas":       positivas,
        "negativas":       negativas,
        "neutras":         neutras,
        "total_ativos":    len(ativos),
    }

    # ── 2. Série temporal por ativo ───────────────────────────────────────────
    # Para cada ativo: datas, scores médios diários, preços de fechamento
    series = {}

    for ativo in ativos:
        noticias_ativo = (
            Noticia.query
            .filter(
                Noticia.ativo_id == ativo.id,
                Noticia.score_sentimento.isnot(None),
                Noticia.data_publicacao >= data_inicio,
            )
            .all()
        )

        if not noticias_ativo:
            continue

        # Agrega score médio por data
        score_por_data = defaultdict(list)
        for n in noticias_ativo:
            d = n.data_publicacao.date()
            score_por_data[d].append(n.score_sentimento)

        datas_score  = sorted(score_por_data.keys())
        scores_medios = [round(sum(score_por_data[d]) / len(score_por_data[d]), 4)
                         for d in datas_score]

        # Cotações no mesmo período
        cotacoes = (
            Cotacao.query
            .filter(
                Cotacao.ativo_id == ativo.id,
                Cotacao.data >= data_inicio,
            )
            .order_by(Cotacao.data)
            .all()
        )

        datas_cot   = [c.data for c in cotacoes]
        precos      = [c.preco_fechamento for c in cotacoes]
        variacoes   = [c.variacao_pct for c in cotacoes]

        series[ativo.ticker] = {
            "nome":          ativo.nome,
            "datas_score":   [str(d) for d in datas_score],
            "scores":        scores_medios,
            "datas_cot":     [str(d) for d in datas_cot],
            "precos":        precos,
            "variacoes":     variacoes,
            "n_noticias":    len(noticias_ativo),
        }

    # ── 3. Heatmap: score médio por ativo × mês ───────────────────────────────
    dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    heatmap_ativos  = []
    heatmap_valores = []  # lista de listas [ativo][dia_semana]

    for ativo in ativos:
        noticias_ativo = (
            Noticia.query
            .filter(
                Noticia.ativo_id == ativo.id,
                Noticia.score_sentimento.isnot(None),
            )
            .all()
        )
        if not noticias_ativo:
            continue

        por_dia: dict[int, list] = defaultdict(list)
        for n in noticias_ativo:
            dow = n.data_publicacao.weekday()  # 0=Seg
            por_dia[dow].append(n.score_sentimento)

        linha = [
            round(sum(por_dia[i]) / len(por_dia[i]), 3) if por_dia[i] else 0.0
            for i in range(7)
        ]
        heatmap_ativos.append(ativo.ticker.replace(".SA", ""))
        heatmap_valores.append(linha)

    heatmap = {
        "ativos":   heatmap_ativos,
        "dias":     dias_semana,
        "valores":  heatmap_valores,
    }

    # ── 4. Tabela de correlações ───────────────────────────────────────────────
    correlacoes_db = (
        Correlacao.query
        .order_by(Correlacao.criado_em.desc())
        .all()
    )

    correlacoes = []
    for c in correlacoes_db:
        ativo = ativo_map.get(c.ativo_id)
        correlacoes.append({
            "ticker":      ativo.ticker if ativo else "—",
            "nome":        ativo.nome   if ativo else "—",
            "pearson":     round(c.pearson,  3) if c.pearson  is not None else None,
            "spearman":    round(c.spearman, 3) if c.spearman is not None else None,
            "n_noticias":  c.n_noticias,
            "periodo":     f"{c.data_inicio} → {c.data_fim}",
            "forca":       _classificar_correlacao(c.pearson),
        })

    # ── 5. Últimas notícias com score ─────────────────────────────────────────
    ultimas = (
        Noticia.query
        .filter(Noticia.score_sentimento.isnot(None))
        .order_by(Noticia.data_publicacao.desc())
        .limit(20)
        .all()
    )

    noticias_lista = []
    for n in ultimas:
        ativo = ativo_map.get(n.ativo_id)
        noticias_lista.append({
            "titulo":   n.titulo,
            "ticker":   ativo.ticker.replace(".SA", "") if ativo else "—",
            "score":    n.score_sentimento,
            "classe":   _classe_score(n.score_sentimento),
            "data":     n.data_publicacao.strftime("%d/%m/%Y"),
            "url":      n.url,
        })

    return {
        "resumo":      resumo,
        "series":      series,
        "series_json": _json(series),
        "heatmap":     heatmap,
        "heatmap_json": _json(heatmap),
        "correlacoes": correlacoes,
        "noticias":    noticias_lista,
        "gerado_em":   date.today().strftime("%d/%m/%Y"),
        "periodo_dias": dias,
    }


def _classificar_correlacao(valor) -> str:
    if valor is None:
        return "—"
    v = abs(valor)
    if v >= 0.5:
        return "forte"
    if v >= 0.3:
        return "moderada"
    return "fraca"


def _classe_score(score) -> str:
    if score is None:
        return "neutro"
    if score > 0.05:
        return "positivo"
    if score < -0.05:
        return "negativo"
    return "neutro"