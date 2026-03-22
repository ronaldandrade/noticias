"""
scraper.py — foco em VALE3, PETR4, ITUB4 + mercado geral BR

Cada feed tem um tickers_hint: notícias daquele feed já nascem com
ativo_id preenchido, sem depender de varredura de texto.
Score de sentimento calculado direto na coleta.
"""

import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime

from .models import Noticia, Ativo
from . import db
from .services.resume_text_service import resumir_texto
from .services.sentimento_service import calcular_score

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}

# ── Fontes RSS ────────────────────────────────────────────────────────────────
# (nome, url, num_frases_resumo, tickers_hint)
FONTES_RSS = [

    # ── Mercado geral / Ibovespa ──────────────────────────────────────────────
    ("G1 Economia",
     "https://g1.globo.com/rss/g1/economia/",
     2, ["^BVSP"]),

    ("CNN Brasil Economia",
     "https://www.cnnbrasil.com.br/economia/feed/",
     2, ["^BVSP"]),

    ("CNN Brasil Finanças",
     "https://www.cnnbrasil.com.br/economia/financas/feed/",
     2, ["^BVSP"]),

    ("Agência Brasil Economia",
     "https://agenciabrasil.ebc.com.br/economia/feed",
     2, ["^BVSP"]),

    ("InfoMoney Mercados",
     "https://www.infomoney.com.br/mercados/feed/",
     2, ["^BVSP"]),

    ("InfoMoney Economia",
     "https://www.infomoney.com.br/economia/feed/",
     2, ["^BVSP"]),

    ("Valor Econômico Finanças",
     "https://valor.globo.com/rss/financas/",
     2, ["^BVSP"]),

    ("Valor Econômico Empresas",
     "https://valor.globo.com/rss/empresas/",
     2, []),

    ("Exame Economia",
     "https://exame.com/feed/",
     2, ["^BVSP"]),

    ("Monitor do Mercado",
     "https://monitordosmercados.com.br/feed/",
     2, ["^BVSP"]),

    ("Suno Research",
     "https://www.sunoresearch.com.br/feed/",
     2, []),

    # ── PETR4 — Petrobras ─────────────────────────────────────────────────────
    ("InfoMoney PETR4",
     "https://www.infomoney.com.br/petr4/feed/",
     2, ["PETR4.SA"]),

    ("Exame Petróleo",
     "https://exame.com/negocios/petroleo/feed/",
     2, ["PETR4.SA"]),

    ("Valor Econômico Petróleo",
     "https://valor.globo.com/empresas/noticia/petrobras.ghtml?formato=rss",
     2, ["PETR4.SA"]),

    ("CNN Brasil Energia",
     "https://www.cnnbrasil.com.br/economia/negocios/feed/",
     2, ["PETR4.SA"]),

    # ── VALE3 — Vale ──────────────────────────────────────────────────────────
    ("InfoMoney VALE3",
     "https://www.infomoney.com.br/vale3/feed/",
     2, ["VALE3.SA"]),

    ("Exame Mineração",
     "https://exame.com/negocios/mineracao/feed/",
     2, ["VALE3.SA"]),

    ("Valor Econômico Vale",
     "https://valor.globo.com/empresas/noticia/vale.ghtml?formato=rss",
     2, ["VALE3.SA"]),

    # ── ITUB4 — Itaú ──────────────────────────────────────────────────────────
    ("InfoMoney ITUB4",
     "https://www.infomoney.com.br/itub4/feed/",
     2, ["ITUB4.SA"]),

    ("InfoMoney Bancos",
     "https://www.infomoney.com.br/bancos/feed/",
     2, ["ITUB4.SA"]),

    ("Valor Econômico Bancos",
     "https://valor.globo.com/financas/noticia/bancos.ghtml?formato=rss",
     2, ["ITUB4.SA"]),

    ("Exame Finanças",
     "https://exame.com/financas/feed/",
     2, ["ITUB4.SA"]),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_data(data_str: str) -> datetime:
    formatos = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    for fmt in formatos:
        try:
            return datetime.strptime(data_str, fmt).replace(tzinfo=None)
        except ValueError:
            continue
    return datetime.now()


def _texto_limpo(tag) -> str:
    if tag is None:
        return ""
    texto = tag.get_text(strip=True)
    if "<" in texto:
        texto = BeautifulSoup(texto, "html.parser").get_text(strip=True)
    return texto or "Sem descrição"


def _ativo_id_por_hint(tickers_hint: list[str], ativos: list[Ativo]) -> int | None:
    for ticker in tickers_hint:
        for ativo in ativos:
            if ativo.ticker == ticker:
                return ativo.id
    return None


# Palavras-chave extras por ativo para varredura de texto
_KEYWORDS: dict[str, list[str]] = {
    "PETR4.SA": ["PETROBRAS", "PETR4", "PETRÓLEO", "PRÉ-SAL", "COMBUSTÍVEL"],
    "VALE3.SA": ["VALE", "VALE3", "MINÉRIO", "MINÉRIO DE FERRO", "PELOTA"],
    "ITUB4.SA": ["ITAÚ", "ITAU", "ITUB4", "ITAÚ UNIBANCO", "BANCO ITAÚ"],
    "^BVSP":    ["IBOVESPA", "BOVESPA", "BVSP", "B3", "BOLSA DE VALORES"],
}

def _ativo_id_por_texto(titulo: str, conteudo: str, ativos: list[Ativo]) -> int | None:
    texto = f"{titulo} {conteudo[:400]}".upper()
    for ativo in ativos:
        keywords = _KEYWORDS.get(ativo.ticker, [])
        ticker_limpo = ativo.ticker.replace(".SA", "").replace("-", "").upper()
        todas = [ticker_limpo, ativo.nome.upper()] + keywords
        if any(kw in texto for kw in todas):
            return ativo.id
    return None


def _raspar_fonte(
    nome: str,
    url: str,
    num_frases: int,
    tickers_hint: list[str],
    ativos: list[Ativo],
) -> list[Noticia]:

    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        resp.encoding = "utf-8"
    except requests.RequestException as exc:
        logger.warning("Falha ao buscar '%s': %s", nome, exc)
        return []

    try:
        soup = BeautifulSoup(resp.text, "xml", from_encoding="utf-8")
    except Exception as exc:
        logger.warning("Falha ao parsear '%s': %s", nome, exc)
        return []

    ativo_id_hint = _ativo_id_por_hint(tickers_hint, ativos)
    noticias = []

    for item in soup.find_all("item"):
        titulo_tag = item.find("title")
        link_tag   = item.find("link")
        desc_tag   = item.find("description")
        data_tag   = item.find("pubDate") or item.find("dc:date")

        if not titulo_tag or not link_tag:
            continue

        titulo   = _texto_limpo(titulo_tag)
        link     = link_tag.get_text(strip=True)
        conteudo = _texto_limpo(desc_tag)
        data_str = data_tag.get_text(strip=True) if data_tag else ""
        data     = _parse_data(data_str) if data_str else datetime.now()

        try:
            resumo = resumir_texto(conteudo, num_frases=num_frases)
        except Exception:
            resumo = conteudo[:200]

        ativo_id = ativo_id_hint or _ativo_id_por_texto(titulo, conteudo, ativos)
        score    = calcular_score(f"{titulo}. {conteudo}")

        noticias.append(Noticia(
            titulo=titulo,
            conteudo=conteudo,
            url=link,
            fonte=nome,
            data_publicacao=data,
            resumo=resumo,
            score_sentimento=score,
            ativo_id=ativo_id,
        ))

    logger.info("'%s': %d notícias.", nome, len(noticias))
    return noticias


# ── Função principal ──────────────────────────────────────────────────────────

def buscar_noticias() -> list[Noticia]:
    ativos = Ativo.query.all()
    todas: list[Noticia] = []

    for nome, url, num_frases, tickers_hint in FONTES_RSS:
        todas.extend(_raspar_fonte(nome, url, num_frases, tickers_hint, ativos))

    urls_vistas: set[str] = set()
    novas: list[Noticia] = []

    for noticia in todas:
        if noticia.url in urls_vistas:
            continue
        urls_vistas.add(noticia.url)
        if not Noticia.query.filter_by(url=noticia.url).first():
            novas.append(noticia)

    if novas:
        try:
            db.session.bulk_save_objects(novas)
            db.session.commit()
            logger.info("Salvas %d novas notícias.", len(novas))
        except Exception as exc:
            db.session.rollback()
            logger.error("Erro ao salvar: %s", exc)
            raise

    # Resumo por ativo no console
    from collections import Counter
    contagem = Counter(n.ativo_id for n in novas if n.ativo_id)
    ativo_map = {a.id: a.ticker for a in ativos}
    sem_ativo = sum(1 for n in novas if n.ativo_id is None)

    print(f"\n  Novas notícias salvas: {len(novas)}")
    for ativo_id, qtd in contagem.most_common():
        print(f"  {ativo_map.get(ativo_id, ativo_id):<14} {qtd} notícias")
    if sem_ativo:
        print(f"  sem ativo associado:  {sem_ativo} notícias")

    return todas