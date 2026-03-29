"""
services/ner_service.py

NER com spaCy pt_core_news_sm para identificar organizações nas notícias
e categorizar notícias sem ativo financeiro.

Instalação:
    pip install spacy
    python -m spacy download pt_core_news_sm
"""

import logging
import re
from typing import Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# ── Categorias para notícias sem ativo financeiro ─────────────────────────────
# Cada categoria tem palavras-chave que disparam no título
CATEGORIAS: dict[str, list[str]] = {
    "política": [
        "lula", "bolsonaro", "alckimin", "governo", "congresso", "senado", "câmara",
        "ministério", "ministro", "presidente", "eleição", "partido",
        "stf", "supremo", "pec", "reforma", "votação", "deputado",
        "senador", "planalto", "oposição", "petista", "federal",
    ],
    "economia_geral": [
        "pib", "inflação", "ipca", "igpm", "selic", "copom", "juros",
        "banco central", "fiscal", "déficit", "superávit", "dívida pública",
        "arrecadação", "receita federal", "orçamento", "balança comercial",
        "exportação", "importação", "câmbio", "desemprego", "emprego",
        "caged", "pnad", "crescimento econômico", "recessão",
    ],
    "mercado_financeiro": [
        "bolsa", "ibovespa", "b3", "ações", "investidor", "mercado",
        "pregão", "alta", "queda", "índice", "fundos", "tesouro direto",
        "renda fixa", "renda variável", "cdi", "debenture", "ipo",
        "follow-on", "dividendo", "resultado", "balanço", "lucro",
    ],
    "internacional": [
        "eua", "estados unidos", "china", "europa", "fed", "banco central europeu",
        "trump", "biden", "xi jinping", "guerra", "ucrânia", "russia",
        "opep", "petróleo", "commodities", "dow jones", "nasdaq", "s&p",
        "fundo monetário", "fmi", "banco mundial", "ocde",
    ],
    "tecnologia": [
        "inteligência artificial", "ia", "chatgpt", "openai", "google",
        "microsoft", "apple", "amazon", "meta", "startup", "fintech",
        "blockchain", "cripto", "nft", "5g", "chip", "semicondutor",
    ],
    "agronegócio": [
        "soja", "milho", "boi", "suíno", "frango", "café", "açúcar",
        "etanol", "grãos", "safra", "embrapa", "cna", "agro",
        "fazenda", "pecuária", "agricultura",
    ],
    "energia": [
        "petróleo", "gás natural", "energia elétrica", "energias renováveis",
        "solar", "eólica", "hidrelétrica", "aneel", "anp", "pré-sal",
        "combustível", "gasolina", "diesel", "etanol",
    ],
    "saúde": [
        "saúde", "sus", "anvisa", "vacina", "remédio", "medicamento",
        "hospital", "plano de saúde", "ans", "pandemia", "vírus",
    ],
    "entretenimento": [
        "futebol", "copa", "olimpíadas", "esporte", "celebridade","big brother",
        "filme", "série", "música", "show", "netflix", "streaming","bbb","BBB"
    ],
}

# ── Mapa de entidades NER → tickers ──────────────────────────────────────────
# Quando o spaCy identifica uma ORG, tentamos mapear para um ticker
ENTIDADE_PARA_TICKER: dict[str, str] = {
    # Petróleo
    "petrobras":          "PETR4.SA",
    "petrobrás":          "PETR4.SA",
    # Vale
    "vale":               "VALE3.SA",
    # Bancos
    "itaú":               "ITUB4.SA",
    "itau":               "ITUB4.SA",
    "itaú unibanco":      "ITUB4.SA",
    "bradesco":           "BBDC4.SA",
    "banco bradesco":     "BBDC4.SA",
    "banco do brasil":    "BBAS3",
    "btg pactual":        "BPAC11",
    "btg":                "BPAC11",
    "xp":                 "XPBR31",
    "xp investimentos":   "XPBR31",
    "santander":          "SANB11",
    "banco inter":        "INBR32",
    "inter":              "INBR32",
    # Telecom
    "oi":                 "OIBR3",
    "tim":                "TIMS3",
    "tim brasil":         "TIMS3",
    "vivo":               "VIVT3",
    "telefônica":         "VIVT3",
    "telefonica":         "VIVT3",
    # Energia
    "eletrobras":         "ELET3",
    "eletrobrás":         "ELET3",
    "cemig":              "CMIG4",
    "equatorial":         "EQTL3",
    # Varejo
    "americanas":         "AMER3",
    "lojas americanas":   "AMER3",
    "magazine luiza":     "MGLU3.SA",
    "magalu":             "MGLU3.SA",
    "renner":             "LREN3",
    "lojas renner":       "LREN3",
    # Mobilidade
    "localiza":           "RENT3",
    # Alimentos
    "jbs":                "JBSS3",
    "ambev":              "ABEV3",
    # Índices / mercado
    "ibovespa":           "^BVSP",
    "b3":                 "^BVSP",
    "bovespa":            "^BVSP",
}


@lru_cache(maxsize=1)
def _carregar_modelo():
    """Carrega o modelo spaCy uma única vez e reutiliza."""
    try:
        import spacy
        nlp = spacy.load("pt_core_news_sm")
        logger.info("Modelo spaCy carregado com sucesso.")
        return nlp
    except OSError:
        logger.error(
            "Modelo spaCy não encontrado. "
            "Rode: python -m spacy download pt_core_news_sm"
        )
        return None
    except ImportError:
        logger.error("spaCy não instalado. Rode: pip install spacy")
        return None


def extrair_entidades(texto: str) -> list[dict]:
    """
    Extrai entidades nomeadas do texto usando spaCy.
    Retorna lista de {"texto": str, "tipo": str, "score": float}
    """
    nlp = _carregar_modelo()
    if not nlp:
        return []

    doc = nlp(texto[:512])  # limita para performance
    entidades = []

    for ent in doc.ents:
        if ent.label_ in ("ORG", "PER", "LOC", "MISC"):
            entidades.append({
                "texto": ent.text.strip(),
                "tipo":  ent.label_,
            })

    return entidades


def identificar_ticker_por_ner(titulo: str, conteudo: str, ativos: list) -> Optional[int]:
    """
    Usa NER para identificar organizações no texto e mapear para tickers.
    Retorna ativo_id ou None.
    """
    ativo_map = {a.ticker: a.id for a in ativos}
    texto = f"{titulo} {conteudo[:300]}"
    entidades = extrair_entidades(texto)

    # Pontuação por ativo via NER
    pontos_ner: dict[str, int] = {}

    for ent in entidades:
        if ent["tipo"] != "ORG":
            continue

        nome_lower = ent["texto"].lower().strip()

        # Busca direta no mapa
        ticker = ENTIDADE_PARA_TICKER.get(nome_lower)

        # Se não encontrou direto, tenta match parcial
        if not ticker:
            for chave, t in ENTIDADE_PARA_TICKER.items():
                if chave in nome_lower or nome_lower in chave:
                    ticker = t
                    break

        if ticker and ticker in ativo_map:
            pontos_ner[ticker] = pontos_ner.get(ticker, 0) + 5

    if not pontos_ner:
        return None

    melhor = max(pontos_ner, key=lambda t: pontos_ner[t])
    return ativo_map.get(melhor)


def categorizar_noticia(titulo: str, conteudo: str) -> str:
    """
    Classifica a notícia em uma categoria temática.
    Usa o título com peso dobrado em relação ao conteúdo.
    Retorna a categoria com maior pontuação ou 'geral' se nenhuma atingir limiar.
    """
    texto_titulo   = titulo.lower()
    texto_conteudo = conteudo[:400].lower()
    pontuacoes: dict[str, int] = {}

    for categoria, keywords in CATEGORIAS.items():
        pontos = 0
        for kw in keywords:
            if kw in texto_titulo:
                pontos += 2   # título vale dobrado
            elif kw in texto_conteudo:
                pontos += 1
        if pontos > 0:
            pontuacoes[categoria] = pontos

    if not pontuacoes:
        return "geral"

    return max(pontuacoes, key=lambda c: pontuacoes[c])


def processar_noticia(titulo: str, conteudo: str, ativos: list,
                      ativo_id_atual: Optional[int]) -> dict:
    """
    Pipeline completo para uma notícia:
    1. Se já tem ativo_id → só categoriza
    2. Se não tem → tenta NER para encontrar ativo
    3. Categoriza independente do resultado

    Retorna: {"ativo_id": int|None, "categoria": str}
    """
    categoria = categorizar_noticia(titulo, conteudo)

    if ativo_id_atual is not None:
        return {"ativo_id": ativo_id_atual, "categoria": categoria}

    # Tenta NER
    ativo_id_ner = identificar_ticker_por_ner(titulo, conteudo, ativos)

    return {
        "ativo_id": ativo_id_ner,
        "categoria": categoria,
    }


def aplicar_ner_em_lote(limite: int = 500) -> dict:
    """
    Aplica NER e categorização nas notícias sem ativo_id
    e em todas as notícias sem categoria.
    Retorna dict com estatísticas da operação.
    """
    from ..models import Noticia, Ativo
    from .. import db

    ativos = Ativo.query.all()

    # Notícias sem ativo — candidatas ao NER
    sem_ativo = (
        Noticia.query
        .filter(Noticia.ativo_id.is_(None))
        .limit(limite)
        .all()
    )

    # Notícias sem categoria (todas)
    sem_categoria = (
        Noticia.query
        .filter(
            Noticia.categoria.is_(None),
            Noticia.ativo_id.isnot(None),  # já tem ativo, só precisa de categoria
        )
        .limit(limite)
        .all()
    )

    stats = {
        "processadas":      0,
        "ativo_encontrado": 0,
        "categorias":       {},
    }

    # Processa notícias sem ativo (NER + categorização)
    for noticia in sem_ativo:
        resultado = processar_noticia(
            noticia.titulo,
            noticia.conteudo or "",
            ativos,
            None,
        )
        noticia.ativo_id  = resultado["ativo_id"]
        noticia.categoria = resultado["categoria"]

        if resultado["ativo_id"]:
            stats["ativo_encontrado"] += 1

        cat = resultado["categoria"]
        stats["categorias"][cat] = stats["categorias"].get(cat, 0) + 1
        stats["processadas"] += 1

    # Categoriza notícias que já têm ativo mas falta categoria
    for noticia in sem_categoria:
        noticia.categoria = categorizar_noticia(
            noticia.titulo, noticia.conteudo or ""
        )
        cat = noticia.categoria
        stats["categorias"][cat] = stats["categorias"].get(cat, 0) + 1
        stats["processadas"] += 1

    try:
        db.session.commit()
        logger.info(
            "NER concluído: %d processadas, %d ativos encontrados.",
            stats["processadas"], stats["ativo_encontrado"],
        )
    except Exception as exc:
        db.session.rollback()
        logger.error("Erro ao salvar NER: %s", exc)
        raise

    return stats