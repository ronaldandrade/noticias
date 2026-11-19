"""
services/ner_service.py

Categorização temática das notícias por palavras-chave (título pesa o dobro).
"""

# ── Categorias temáticas ──────────────────────────────────────────────────────
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


def aplicar_categorias_em_lote(limite: int = 500) -> dict:
    """Categoriza as notícias que ainda não têm categoria."""
    from ..models import Noticia
    from .. import db

    noticias = Noticia.query.filter(Noticia.categoria.is_(None)).limit(limite).all()
    categorias: dict[str, int] = {}
    for n in noticias:
        n.categoria = categorizar_noticia(n.titulo, n.conteudo or "")
        categorias[n.categoria] = categorias.get(n.categoria, 0) + 1
    db.session.commit()
    return {"processadas": len(noticias), "categorias": categorias}
