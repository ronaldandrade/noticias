"""
scraper.py — raspagem HTML direta (sem RSS)

Sites: InfoMoney, G1 Economia, Exame, UOL Economia

"""

import logging
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin

from .models import Noticia, Ativo
from . import db
from .services.resume_text_service import resumir_texto
from .services.sentimento_service import calcular_score
from .services.assossiacao_service import associar_ativo

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 8
DELAY_ENTRE_SITES = 1.5  # segundos — evita bloqueio por rate limit

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── Configuração das fontes ───────────────────────────────────────────────────
# Cada fonte define:
#   url          → página a raspar
#   ticker_hint  → ativo associado a todas as notícias desse feed (ou None)
#   seletor_item → CSS que aponta cada card/item de notícia na página
#   seletor_titulo → CSS relativo ao item que contém o título
#   seletor_link → CSS relativo ao item que contém o link (ou None = usar o próprio item)
#   base_url     → prefixo para links relativos

FONTES_HTML = [

    # ── InfoMoney por ticker ───────────────────────────────────────────────────
    {
        "nome": "InfoMoney PETR4",
        "url": "https://www.infomoney.com.br/tudo-sobre/petrobras/",
        "ticker_hint": "PETR4.SA",
        "seletor_item": "article.blocco, div.card-news, h2.title-news",
        "seletor_titulo": "h2, h3, .title, a",
        "base_url": "https://www.infomoney.com.br",
    },
    {
        "nome": "InfoMoney VALE3",
        "url": "https://www.infomoney.com.br/tudo-sobre/vale/",
        "ticker_hint": "VALE3.SA",
        "seletor_item": "article.blocco, div.card-news, h2.title-news",
        "seletor_titulo": "h2, h3, .title, a",
        "base_url": "https://www.infomoney.com.br",
    },
    {
        "nome": "InfoMoney ITUB4",
        "url": "https://www.infomoney.com.br/tudo-sobre/itau/",
        "ticker_hint": "ITUB4.SA",
        "seletor_item": "article.blocco, div.card-news, h2.title-news",
        "seletor_titulo": "h2, h3, .title, a",
        "base_url": "https://www.infomoney.com.br",
    },
    {
        "nome": "InfoMoney Mercados",
        "url": "https://www.infomoney.com.br/mercados/",
        "ticker_hint": "^BVSP",
        "seletor_item": "article.blocco, div.card-news",
        "seletor_titulo": "h2, h3, .title",
        "base_url": "https://www.infomoney.com.br",
    },

    # ── G1 Economia ───────────────────────────────────────────────────────────
    {
        "nome": "G1 Economia",
        "url": "https://g1.globo.com/economia/",
        "ticker_hint": "^BVSP",
        "seletor_item": "div.feed-post, div.bastian-feed-item",
        "seletor_titulo": "a.feed-post-link, .gui-color-primary",
        "base_url": "https://g1.globo.com",
    },

    # ── Exame ─────────────────────────────────────────────────────────────────
    {
        "nome": "Exame Economia",
        "url": "https://exame.com/economia/",
        "ticker_hint": "^BVSP",
        "seletor_item": "article, div.card",
        "seletor_titulo": "h2, h3, a",
        "base_url": "https://exame.com",
    },
    {
        "nome": "Exame Mercados",
        "url": "https://exame.com/invest/mercados/",
        "ticker_hint": "^BVSP",
        "seletor_item": "article, div.card",
        "seletor_titulo": "h2, h3, a",
        "base_url": "https://exame.com",
    },
    {
        "nome": "Exame Petróleo & Energia",
        "url": "https://exame.com/invest/commodities/petroleo/",
        "ticker_hint": "PETR4.SA",
        "seletor_item": "article, div.card",
        "seletor_titulo": "h2, h3, a",
        "base_url": "https://exame.com",
    },

    # ── UOL Economia ──────────────────────────────────────────────────────────
    {
        "nome": "UOL Economia",
        "url": "https://economia.uol.com.br/",
        "ticker_hint": "^BVSP",
        "seletor_item": "article, div.thumbnails-item",
        "seletor_titulo": "h2, h3, .title",
        "base_url": "https://economia.uol.com.br",
    },

    # ── Suno ──────────────────────────────────────────────────────────────────
    {
        "nome": "Suno Notícias",
        "url": "https://www.suno.com.br/noticias/",
        "ticker_hint": None,
        "seletor_item": "article, div.post-card",
        "seletor_titulo": "h2, h3, .entry-title",
        "base_url": "https://www.suno.com.br",
    },
    {
        "nome": "Suno PETR4",
        "url": "https://www.suno.com.br/acoes/petr4/",
        "ticker_hint": "PETR4.SA",
        "seletor_item": "article, div.post-card",
        "seletor_titulo": "h2, h3, .entry-title",
        "base_url": "https://www.suno.com.br",
    },
    {
        "nome": "Suno VALE3",
        "url": "https://www.suno.com.br/acoes/vale3/",
        "ticker_hint": "VALE3.SA",
        "seletor_item": "article, div.post-card",
        "seletor_titulo": "h2, h3, .entry-title",
        "base_url": "https://www.suno.com.br",
    },
    {
        "nome": "Suno ITUB4",
        "url": "https://www.suno.com.br/acoes/itub4/",
        "ticker_hint": "ITUB4.SA",
        "seletor_item": "article, div.post-card",
        "seletor_titulo": "h2, h3, .entry-title",
        "base_url": "https://www.suno.com.br",
    },

    # ── RSS que ainda funcionam (mantidos como fallback) ──────────────────────
    {
        "nome": "G1 RSS",
        "url": "https://g1.globo.com/rss/g1/economia/",
        "ticker_hint": "^BVSP",
        "seletor_item": None,  # sinaliza modo RSS
        "seletor_titulo": None,
        "base_url": "",
    },
    {
        "nome": "InfoMoney RSS Mercados",
        "url": "https://www.infomoney.com.br/mercados/feed/",
        "ticker_hint": "^BVSP",
        "seletor_item": None,
        "seletor_titulo": None,
        "base_url": "",
    },
    {
        "nome": "Exame RSS",
        "url": "https://exame.com/feed/",
        "ticker_hint": "^BVSP",
        "seletor_item": None,
        "seletor_titulo": None,
        "base_url": "",
    },
    {
        "nome": "UOL RSS Economia",
        "url": "https://rss.uol.com.br/feed/economia.xml",
        "ticker_hint": "^BVSP",
        "seletor_item": None,
        "seletor_titulo": None,
        "base_url": "",
    },
    {
        "nome": "Livecoins RSS",
        "url": "https://livecoins.com.br/feed/",
        "ticker_hint": None,
        "seletor_item": None,
        "seletor_titulo": None,
        "base_url": "",
    },
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


def _ativo_id_por_hint(ticker_hint: str | None, ativos: list[Ativo]) -> int | None:
    if not ticker_hint:
        return None
    for ativo in ativos:
        if ativo.ticker == ticker_hint:
            return ativo.id
    return None



def _fazer_request(url: str) -> requests.Response | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp
    except requests.RequestException as exc:
        logger.warning("Falha ao buscar '%s': %s", url, exc)
        return None


# ── Raspagem RSS ──────────────────────────────────────────────────────────────

def _raspar_rss(fonte: dict, ativos: list[Ativo]) -> list[dict]:
    resp = _fazer_request(fonte["url"])
    if not resp:
        return []

    resp.encoding = "utf-8"
    try:
        soup = BeautifulSoup(resp.text, "xml", from_encoding="utf-8")
    except Exception:
        return []

    ativo_id_hint = _ativo_id_por_hint(fonte["ticker_hint"], ativos)
    itens = []

    for item in soup.find_all("item"):
        titulo_tag = item.find("title")
        link_tag   = item.find("link")
        desc_tag   = item.find("description")
        data_tag   = item.find("pubDate") or item.find("dc:date")

        if not titulo_tag or not link_tag:
            continue

        titulo   = titulo_tag.get_text(strip=True)
        link     = link_tag.get_text(strip=True)
        conteudo = desc_tag.get_text(strip=True) if desc_tag else ""
        if "<" in conteudo:
            conteudo = BeautifulSoup(conteudo, "html.parser").get_text(strip=True)

        data_str = data_tag.get_text(strip=True) if data_tag else ""
        data     = _parse_data(data_str) if data_str else datetime.now()

        itens.append({
            "titulo": titulo, "link": link,
            "conteudo": conteudo, "data": data,
            "ativo_id_hint": ativo_id_hint,
        })

    logger.info("RSS '%s': %d itens.", fonte["nome"], len(itens))
    return itens


# ── Raspagem HTML ─────────────────────────────────────────────────────────────

def _raspar_html(fonte: dict, ativos: list[Ativo]) -> list[dict]:
    resp = _fazer_request(fonte["url"])
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    ativo_id_hint = _ativo_id_por_hint(fonte["ticker_hint"], ativos)
    base_url = fonte["base_url"]
    itens = []
    vistos: set[str] = set()

    # Tenta os seletores de item
    cards = soup.select(fonte["seletor_item"])

    # Fallback genérico se o seletor não encontrar nada
    if not cards:
        cards = soup.select("article") or soup.select("div.post") or soup.select("li.item")

    for card in cards[:15]:  # máximo 15 por página
        # Extrai título
        titulo_el = card.select_one(fonte["seletor_titulo"])
        if not titulo_el:
            titulo_el = card.select_one("a")
        if not titulo_el:
            continue

        titulo = titulo_el.get_text(strip=True)
        if not titulo or len(titulo) < 10:
            continue

        # Extrai link
        link_el = card.select_one("a[href]") or (titulo_el if titulo_el.name == "a" else None)
        if not link_el:
            continue

        href = link_el.get("href", "")
        if not href or href == "#":
            continue

        link = urljoin(base_url, href) if href.startswith("/") else href

        if link in vistos:
            continue
        vistos.add(link)

        # Extrai descrição/conteúdo do card (resumo curto)
        desc_el = card.select_one("p, .description, .summary, .excerpt")
        conteudo = desc_el.get_text(strip=True) if desc_el else titulo

        itens.append({
            "titulo": titulo, "link": link,
            "conteudo": conteudo, "data": datetime.now(),
            "ativo_id_hint": ativo_id_hint,
        })

    logger.info("HTML '%s': %d itens.", fonte["nome"], len(itens))
    return itens


# ── Montagem de Noticia ───────────────────────────────────────────────────────

def _montar_noticia(item: dict, fonte_nome: str, ativos: list[Ativo], num_frases: int) -> Noticia:
    titulo   = item["titulo"]
    conteudo = item["conteudo"]
    ativo_id = item["ativo_id_hint"] or associar_ativo(titulo, conteudo, ativos)
    score    = calcular_score(f"{titulo}. {conteudo}")

    try:
        resumo = resumir_texto(conteudo, num_frases=num_frases)
    except Exception:
        resumo = conteudo[:200]

    return Noticia(
        titulo=titulo,
        conteudo=conteudo,
        url=item["link"],
        # fonte=fonte_nome,
        data_publicacao=item["data"],
        resumo=resumo,
        score_sentimento=score,
        ativo_id=ativo_id,
    )


# ── Função principal ──────────────────────────────────────────────────────────

def buscar_noticias() -> list[Noticia]:
    ativos = Ativo.query.all()
    todas_raw: list[tuple[dict, str]] = []  # (item_dict, nome_fonte)

    for fonte in FONTES_HTML:
        # Decide modo: RSS (seletor_item=None) ou HTML
        if fonte["seletor_item"] is None:
            itens = _raspar_rss(fonte, ativos)
        else:
            itens = _raspar_html(fonte, ativos)

        for item in itens:
            todas_raw.append((item, fonte["nome"]))

        time.sleep(DELAY_ENTRE_SITES)

    # Deduplicação por URL + filtro contra banco
    urls_vistas: set[str] = set()
    novas: list[Noticia] = []

    for item, nome_fonte in todas_raw:
        url = item["link"]
        if url in urls_vistas:
            continue
        urls_vistas.add(url)

        if Noticia.query.filter_by(url=url).first():
            continue

        noticia = _montar_noticia(item, nome_fonte, ativos, num_frases=2)
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

    # Resumo no console
    from collections import Counter
    ativo_map = {a.id: a.ticker for a in ativos}
    contagem  = Counter(n.ativo_id for n in novas if n.ativo_id)
    sem_ativo = sum(1 for n in novas if n.ativo_id is None)

    print(f"\n  Novas notícias salvas: {len(novas)}")
    for ativo_id, qtd in contagem.most_common():
        print(f"  {ativo_map.get(ativo_id, ativo_id):<14} {qtd} notícias")
    if sem_ativo:
        print(f"  sem ativo associado:   {sem_ativo} notícias")

    return novas