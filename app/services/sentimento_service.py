"""
services/sentimento_service.py 

Cálculo de score de sentimento para notícias financeiras.
Combina análise VADER com um léxico financeiro customizado (PT+EN).
"""

import logging
import re
from typing import Optional

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from ..models import Ativo, Noticia
from .. import db
from .assossiacao_service import associar_ativo

logger = logging.getLogger(__name__)

_analyzer = SentimentIntensityAnalyzer()

# Léxico financeiro PT+EN — pesos de -4.0 a +4.0
LEXICO_FINANCEIRO = {
    # Positivos PT
    "lucro": 2.5, "lucros": 2.5, "alta": 1.8, "altas": 1.8,
    "valorização": 2.2, "valorizou": 2.0, "crescimento": 2.0,
    "cresceu": 1.8, "recorde": 2.5, "máxima": 1.5,
    "recuperação": 1.8, "recuperou": 1.6, "dividendo": 1.5,
    "dividendos": 1.5, "aprovação": 1.5, "aprovado": 1.3,
    "expansão": 1.8, "superou": 2.0, "positivo": 1.5,
    "otimismo": 2.0, "acelerou": 1.5, "contrato": 1.2,
    "ganhos": 2.0, "supera": 2.0, "subiu": 1.8, "sobe": 1.5,
    "resultado": 1.2, "resultados": 1.2, "melhora": 1.5,
    "recompra": 1.5, "investimento": 1.2, "captação": 1.2,
    # Negativos PT
    "queda": -1.8, "quedas": -1.8, "baixa": -1.5, "baixas": -1.5,
    "prejuízo": -2.5, "prejuízos": -2.5, "perda": -2.0, "perdas": -2.0,
    "recessão": -2.5, "inflação": -1.5, "crise": -2.5, "colapso": -3.0,
    "calote": -3.0, "default": -2.8, "falência": -3.5,
    "insolvência": -3.0, "desacelerou": -1.8, "contração": -2.0,
    "negativo": -1.5, "pessimismo": -2.0, "caiu": -1.8, "cai": -1.5,
    "rebaixamento": -2.5, "rebaixou": -2.3, "multa": -1.8,
    "investigação": -1.5, "fraude": -3.0, "escândalo": -2.8,
    "demissão": -1.5, "demissões": -1.8, "corte": -1.2, "cortes": -1.2,
    "rombo": -2.5, "dívida": -1.2, "endividamento": -1.5,
    "inadimplência": -2.0, "desvalorização": -2.0,
    # Positivos EN
    "profit": 2.5, "gains": 2.0, "growth": 2.0, "record": 2.5,
    "dividend": 1.5, "rally": 2.0, "surge": 2.0, "beat": 1.8,
    "upgrade": 2.0, "bullish": 2.2, "recovery": 1.8,
    # Negativos EN
    "loss": -2.0, "losses": -2.0, "decline": -1.8, "crash": -3.0,
    "bankruptcy": -3.5, "fraud": -3.0, "downgrade": -2.3,
    "bearish": -2.2, "recession": -2.5, "selloff": -2.0,
    "slump": -1.8, "plunge": -2.5,
}

_analyzer.lexicon.update(LEXICO_FINANCEIRO)


def calcular_score(texto: str) -> float:
    """
    Retorna score entre -1.0 e +1.0.
    Combina VADER com léxico financeiro PT/EN. 100% local, sem HTTP.
    """
    if not texto or not texto.strip():
        return 0.0

    score_vader = _analyzer.polarity_scores(texto)["compound"]

    palavras = re.findall(r"\b\w+\b", texto.lower())
    scores_lexico = [LEXICO_FINANCEIRO[p] for p in palavras if p in LEXICO_FINANCEIRO]

    if scores_lexico:
        score_lexico = max(-1.0, min(1.0, sum(scores_lexico) / (len(scores_lexico) * 4)))
        return round(0.6 * score_vader + 0.4 * score_lexico, 4)

    return round(score_vader, 4)



def aplicar_scores_em_lote(limite: int = 500) -> int:
    noticias = (
        Noticia.query
        .filter(Noticia.score_sentimento.is_(None))
        .limit(limite)
        .all()
    )

    if not noticias:
        logger.info("Nenhuma notícia sem score.")
        return 0

    ativos = Ativo.query.all()
    atualizadas = 0

    for i, noticia in enumerate(noticias):
        try:
            texto = f"{noticia.titulo}. {noticia.conteudo}"
            noticia.score_sentimento = calcular_score(texto)

            if noticia.ativo_id is None:
                noticia.ativo_id = associar_ativo(noticia.titulo, noticia.conteudo or "", ativos)

            atualizadas += 1

            if i % 100 == 0 and i > 0:
                db.session.commit()
                print(f"   {i}/{len(noticias)} processadas...", flush=True)

        except Exception as exc:
            logger.warning("Erro na notícia id=%s: %s", noticia.id, exc)

    db.session.commit()
    return atualizadas


def resetar_scores() -> None:
    db.session.query(Noticia).update(
        {Noticia.score_sentimento: None, Noticia.ativo_id: None}
    )
    db.session.commit()