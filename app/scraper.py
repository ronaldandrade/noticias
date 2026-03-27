"""
scraper.py — coleta paralela com ThreadPoolExecutor

Cada fonte roda em uma thread separada.
Com MAX_WORKERS=4, o tempo cai de ~40s para ~10-12s.
"""

import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import Noticia, Ativo
from . import db
from .services.resume_text_service import resumir_texto
from .services.sentimento_service import calcular_score
from .services.assossiacao_service import associar_ativo

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 8      # sites lentos não travam o pool
MAX_WORKERS     = 4      # threads paralelas — seguro para Render free (512MB)
MAX_CARDS       = 15     # itens por fonte — limita uso de memória

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── Fontes ────────────────────────────────────────────────────────────────────
# hint_forte=True  → feed dedicado a um ativo (todas as notícias são sobre ele)
# hint_forte=False → feed geral (hint só é fallback, notícia irrelevante fica sem ativo)
FONTES_HTML = [

    # ── InfoMoney por ativo — hint FORTE ──────────────────────────────────────
    {"nome": "InfoMoney PETR4", "url": "https://www.infomoney.com.br/tudo-sobre/petrobras/",
     "ticker_hint": "PETR4.SA", "hint_forte": True,
     "seletor_item": "article.blocco, div.card-news",
     "seletor_titulo": "h2, h3, .title, a", "base_url": "https://www.infomoney.com.br"},

    {"nome": "InfoMoney VALE3", "url": "https://www.infomoney.com.br/tudo-sobre/vale/",
     "ticker_hint": "VALE3.SA", "hint_forte": True,
     "seletor_item": "article.blocco, div.card-news",
     "seletor_titulo": "h2, h3, .title, a", "base_url": "https://www.infomoney.com.br"},

    {"nome": "InfoMoney ITUB4", "url": "https://www.infomoney.com.br/tudo-sobre/itau/",
     "ticker_hint": "ITUB4.SA", "hint_forte": True,
     "seletor_item": "article.blocco, div.card-news",
     "seletor_titulo": "h2, h3, .title, a", "base_url": "https://www.infomoney.com.br"},

    {"nome": "InfoMoney Mercados", "url": "https://www.infomoney.com.br/mercados/",
     "ticker_hint": "^BVSP", "hint_forte": False,
     "seletor_item": "article.blocco, div.card-news",
     "seletor_titulo": "h2, h3, .title", "base_url": "https://www.infomoney.com.br"},

    # ── Suno ──────────────────────────────────────────────────────────────────
    {"nome": "Suno PETR4", "url": "https://www.suno.com.br/acoes/petr4/",
     "ticker_hint": "PETR4.SA", "hint_forte": True,
     "seletor_item": "article, div.post-card",
     "seletor_titulo": "h2, h3, .entry-title", "base_url": "https://www.suno.com.br"},

    {"nome": "Suno VALE3", "url": "https://www.suno.com.br/acoes/vale3/",
     "ticker_hint": "VALE3.SA", "hint_forte": True,
     "seletor_item": "article, div.post-card",
     "seletor_titulo": "h2, h3, .entry-title", "base_url": "https://www.suno.com.br"},

    {"nome": "Suno ITUB4", "url": "https://www.suno.com.br/acoes/itub4/",
     "ticker_hint": "ITUB4.SA", "hint_forte": True,
     "seletor_item": "article, div.post-card",
     "seletor_titulo": "h2, h3, .entry-title", "base_url": "https://www.suno.com.br"},

    {"nome": "Suno Notícias", "url": "https://www.suno.com.br/noticias/",
     "ticker_hint": None, "hint_forte": False,
     "seletor_item": "article, div.post-card",
     "seletor_titulo": "h2, h3, .entry-title", "base_url": "https://www.suno.com.br"},

    # ── Seções gerais — hint FRACO ────────────────────────────────────────────
    {"nome": "G1 Economia", "url": "https://g1.globo.com/economia/",
     "ticker_hint": "^BVSP", "hint_forte": False,
     "seletor_item": "div.feed-post, div.bastian-feed-item",
     "seletor_titulo": "a.feed-post-link, .gui-color-primary",
     "base_url": "https://g1.globo.com"},

    {"nome": "Exame Economia", "url": "https://exame.com/economia/",
     "ticker_hint": "^BVSP", "hint_forte": False,
     "seletor_item": "article, div.card",
     "seletor_titulo": "h2, h3, a", "base_url": "https://exame.com"},

    {"nome": "Exame Mercados", "url": "https://exame.com/invest/mercados/",
     "ticker_hint": "^BVSP", "hint_forte": False,
     "seletor_item": "article, div.card",
     "seletor_titulo": "h2, h3, a", "base_url": "https://exame.com"},

    # ── RSS ───────────────────────────────────────────────────────────────────
    {"nome": "G1 RSS", "url": "https://g1.globo.com/rss/g1/economia/",
     "ticker_hint": "^BVSP", "hint_forte": False,
     "seletor_item": None, "seletor_titulo": None, "base_url": ""},

    {"nome": "InfoMoney RSS", "url": "https://www.infomoney.com.br/mercados/feed/",
     "ticker_hint": "^BVSP", "hint_forte": False,
     "seletor_item": None, "seletor_titulo": None, "base_url": ""},

    {"nome": "Exame RSS", "url": "https://exame.com/feed/",
     "ticker_hint": "^BVSP", "hint_forte": False,
     "seletor_item": None, "seletor_titulo": None, "base_url": ""},

    {"nome": "UOL RSS", "url": "https://rss.uol.com.br/feed/economia.xml",
     "ticker_hint": "^BVSP", "hint_forte": False,
     "seletor_item": None, "seletor_titulo": None, "base_url": ""},

    {"nome": "Livecoins RSS", "url": "https://livecoins.com.br/feed/",
     "ticker_hint": "BTC-USD", "hint_forte": True,
     "seletor_item": None, "seletor_titulo": None, "base_url": ""},
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_data(data_str: str) -> datetime:
    for fmt in [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ]:
        try:
            return datetime.strptime(data_str, fmt).replace(tzinfo=None)
        except ValueError:
            continue
    return datetime.now()


def _fazer_request(url: str) -> requests.Response | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp
    except requests.RequestException as exc:
        logger.warning("Falha ao buscar '%s': %s", url, exc)
        return None


def _ativo_id_por_hint(ticker_hint: str | None, ativos: list) -> int | None:
    if not ticker_hint:
        return None
    for a in ativos:
        if a.ticker == ticker_hint:
            return a.id
    return None


# ── Raspagem RSS ───────────────────────────────────────────────────────────────

def _raspar_rss(fonte: dict, ativos: list) -> list[dict]:
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
        itens.append({
            "titulo": titulo, "link": link, "conteudo": conteudo,
            "data": _parse_data(data_str) if data_str else datetime.now(),
            "ativo_id_hint": ativo_id_hint, "hint_forte": fonte["hint_forte"],
        })

    logger.info("RSS '%s': %d itens.", fonte["nome"], len(itens))
    return itens


# ── Raspagem HTML ──────────────────────────────────────────────────────────────

def _raspar_html(fonte: dict, ativos: list) -> list[dict]:
    resp = _fazer_request(fonte["url"])
    if not resp:
        return []

    soup     = BeautifulSoup(resp.text, "html.parser")
    base_url = fonte["base_url"]
    ativo_id_hint = _ativo_id_por_hint(fonte["ticker_hint"], ativos)
    itens  = []
    vistos: set[str] = set()

    cards = soup.select(fonte["seletor_item"])
    if not cards:
        cards = soup.select("article") or soup.select("div.post") or soup.select("li.item")

    for card in cards[:MAX_CARDS]:
        titulo_el = card.select_one(fonte["seletor_titulo"]) or card.select_one("a")
        if not titulo_el:
            continue

        titulo = titulo_el.get_text(strip=True)
        if not titulo or len(titulo) < 10:
            continue

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

        desc_el  = card.select_one("p, .description, .summary, .excerpt")
        conteudo = desc_el.get_text(strip=True) if desc_el else titulo

        itens.append({
            "titulo": titulo, "link": link, "conteudo": conteudo,
            "data": datetime.now(),
            "ativo_id_hint": ativo_id_hint, "hint_forte": fonte["hint_forte"],
        })

    logger.info("HTML '%s': %d itens.", fonte["nome"], len(itens))
    return itens


# ── Worker por fonte ───────────────────────────────────────────────────────────

def _processar_fonte(fonte: dict, ativos: list) -> list[dict]:
    try:
        if fonte["seletor_item"] is None:
            return _raspar_rss(fonte, ativos)
        return _raspar_html(fonte, ativos)
    except Exception as exc:
        logger.error("Erro na fonte '%s': %s", fonte["nome"], exc)
        return []


# ── Montagem de Noticia ────────────────────────────────────────────────────────

def _montar_noticia(item: dict, fonte_nome: str, ativos: list) -> Noticia:
    titulo   = item["titulo"]
    conteudo = item["conteudo"]

    # Algoritmo de pontuação sempre primeiro
    ativo_id = associar_ativo(titulo, conteudo, ativos)

    # Só usa hint se o algoritmo não encontrou E o feed é dedicado ao ativo
    if ativo_id is None and item.get("hint_forte") and item.get("ativo_id_hint"):
        ativo_id = item["ativo_id_hint"]

    score = calcular_score(f"{titulo}. {conteudo}")

    try:
        resumo = resumir_texto(conteudo, num_frases=2)
    except Exception:
        resumo = conteudo[:200]

    return Noticia(
        titulo=titulo, 
        conteudo=conteudo,
        url=item["link"], 
        data_publicacao=item["data"], 
        resumo=resumo,
        score_sentimento=score, 
        ativo_id=ativo_id,
    )


# ── Função principal ───────────────────────────────────────────────────────────

def buscar_noticias() -> list[Noticia]:
    """
    Raspa todas as fontes em paralelo (ThreadPoolExecutor).
    Tempo esperado: ~10-12s com MAX_WORKERS=4 vs ~40s sequencial.
    """
    ativos = Ativo.query.all()
    todas_raw: list[tuple[dict, str]] = []
    inicio = datetime.now()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futuros = {
            executor.submit(_processar_fonte, fonte, ativos): fonte["nome"]
            for fonte in FONTES_HTML
        }
        for futuro in as_completed(futuros):
            nome = futuros[futuro]
            try:
                for item in futuro.result():
                    todas_raw.append((item, nome))
            except Exception as exc:
                logger.error("Fonte '%s' falhou: %s", nome, exc)

    duracao = (datetime.now() - inicio).seconds
    logger.info("Coleta paralela: %ds — %d itens brutos.", duracao, len(todas_raw))

    # Deduplicação + filtro contra banco
    urls_vistas: set[str] = set()
    novas: list[Noticia] = []

    for item, nome_fonte in todas_raw:
        url = item["link"]
        if url in urls_vistas:
            continue
        urls_vistas.add(url)
        if Noticia.query.filter_by(url=url).first():
            continue
        novas.append(_montar_noticia(item, nome_fonte, ativos))

    if novas:
        try:
            db.session.add_all(novas)   
            db.session.commit()
            logger.info(f"Sucesso: {len(novas)} notícias salvas.")
        except Exception as exc:
            db.session.rollback()
            logger.error(f"Erro ao salvar: {exc}")
    from collections import Counter
    ativo_map = {a.id: a.ticker for a in ativos}
    contagem  = Counter(n.ativo_id for n in novas if n.ativo_id)
    sem_ativo = sum(1 for n in novas if n.ativo_id is None)

    print(f"\n  Coleta em {duracao}s — {len(novas)} notícias novas")
    for ativo_id, qtd in contagem.most_common():
        print(f"  {ativo_map.get(ativo_id, ativo_id):<14} {qtd}")
    if sem_ativo:
        print(f"  sem ativo:           {sem_ativo}")

    return novas