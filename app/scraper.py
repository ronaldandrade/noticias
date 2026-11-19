"""
scraper.py — coleta paralela com ThreadPoolExecutor

Cada fonte roda em uma thread separada.
Com MAX_WORKERS=4, o tempo cai de ~40s para ~10-12s.
"""

import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import Noticia
from . import db
from .services.resume_text_service import resumir_texto
from .services.sentimento_service import calcular_score
from .services.ner_service import categorizar_noticia


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
FONTES_HTML = [

    # ── InfoMoney por tema ──────────────────────────────────────
    {"nome": "InfoMoney PETR4", "url": "https://www.infomoney.com.br/tudo-sobre/petrobras/",
     "seletor_item": "article.blocco, div.card-news",
     "seletor_titulo": "h2, h3, .title, a", "base_url": "https://www.infomoney.com.br"},

    {"nome": "InfoMoney VALE3", "url": "https://www.infomoney.com.br/tudo-sobre/vale/",
     "seletor_item": "article.blocco, div.card-news",
     "seletor_titulo": "h2, h3, .title, a", "base_url": "https://www.infomoney.com.br"},

    {"nome": "InfoMoney ITUB4", "url": "https://www.infomoney.com.br/tudo-sobre/itau/",
     "seletor_item": "article.blocco, div.card-news",
     "seletor_titulo": "h2, h3, .title, a", "base_url": "https://www.infomoney.com.br"},

    {"nome": "InfoMoney Mercados", "url": "https://www.infomoney.com.br/mercados/",
     "seletor_item": "article.blocco, div.card-news",
     "seletor_titulo": "h2, h3, .title", "base_url": "https://www.infomoney.com.br"},

    # ── Suno ──────────────────────────────────────────────────────────────────
    {"nome": "Suno PETR4", "url": "https://www.suno.com.br/acoes/petr4/",
     "seletor_item": "article, div.post-card",
     "seletor_titulo": "h2, h3, .entry-title", "base_url": "https://www.suno.com.br"},

    {"nome": "Suno VALE3", "url": "https://www.suno.com.br/acoes/vale3/",
     "seletor_item": "article, div.post-card",
     "seletor_titulo": "h2, h3, .entry-title", "base_url": "https://www.suno.com.br"},

    {"nome": "Suno ITUB4", "url": "https://www.suno.com.br/acoes/itub4/",
     "seletor_item": "article, div.post-card",
     "seletor_titulo": "h2, h3, .entry-title", "base_url": "https://www.suno.com.br"},

    {"nome": "Suno Notícias", "url": "https://www.suno.com.br/noticias/",
     "seletor_item": "article, div.post-card",
     "seletor_titulo": "h2, h3, .entry-title", "base_url": "https://www.suno.com.br"},

    # ── Seções gerais ────────────────────────────────────────────
    {"nome": "G1 Economia", "url": "https://g1.globo.com/economia/",
     "seletor_item": "div.feed-post, div.bastian-feed-item",
     "seletor_titulo": "a.feed-post-link, .gui-color-primary",
     "base_url": "https://g1.globo.com"},

    {"nome": "Exame Economia", "url": "https://exame.com/economia/",
     "seletor_item": "article, div.card",
     "seletor_titulo": "h2, h3, a", "base_url": "https://exame.com"},

    {"nome": "Exame Mercados", "url": "https://exame.com/invest/mercados/",
     "seletor_item": "article, div.card",
     "seletor_titulo": "h2, h3, a", "base_url": "https://exame.com"},

    # ── RSS ───────────────────────────────────────────────────────────────────
    {"nome": "G1 RSS", "url": "https://g1.globo.com/rss/g1/economia/",
     "seletor_item": None, "seletor_titulo": None, "base_url": ""},

    {"nome": "InfoMoney RSS", "url": "https://www.infomoney.com.br/mercados/feed/",
     "seletor_item": None, "seletor_titulo": None, "base_url": ""},

    {"nome": "Exame RSS", "url": "https://exame.com/feed/",
     "seletor_item": None, "seletor_titulo": None, "base_url": ""},

    {"nome": "UOL RSS", "url": "https://rss.uol.com.br/feed/economia.xml",
     "seletor_item": None, "seletor_titulo": None, "base_url": ""},

    {"nome": "Livecoins RSS", "url": "https://livecoins.com.br/feed/",
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


def _decodificar(resp: requests.Response) -> str:
    """Decodifica o corpo: UTF-8 estrito; se falhar, usa o charset do header
    (ex.: UOL serve ISO-8859-1) ou cp1252 como último recurso."""
    try:
        return resp.content.decode("utf-8")
    except UnicodeDecodeError:
        pass
    m = re.search(r"charset=([\w-]+)", resp.headers.get("content-type", ""), re.I)
    for enc in (m.group(1) if m else None, "cp1252"):
        if not enc:
            continue
        try:
            return resp.content.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return resp.content.decode("utf-8", errors="replace")


# ── Raspagem RSS ───────────────────────────────────────────────────────────────

def _raspar_rss(fonte: dict) -> list[dict]:
    resp = _fazer_request(fonte["url"])
    if not resp:
        return []
    try:
        soup = BeautifulSoup(_decodificar(resp), "xml")
    except Exception:
        return []

    itens = []

    for item in soup.find_all("item"):
        titulo_tag = item.find("title")
        link_tag   = item.find("link")
        desc_tag   = item.find("description")
        data_tag   = item.find("pubDate") or item.find("dc:date")

        if not titulo_tag or not link_tag:
            continue

        titulo   = str(titulo_tag.get_text(strip=True)) if titulo_tag else ""
        link     = str(link_tag.get_text(strip=True)) if link_tag else ""
        conteudo = str(desc_tag.get_text(strip=True)) if desc_tag else ""
        if "<" in conteudo:
            conteudo = str(BeautifulSoup(conteudo, "html.parser").get_text(strip=True))

        data_str = str(data_tag.get_text(strip=True)) if data_tag else ""
        itens.append({
            "titulo": titulo, "link": link, "conteudo": conteudo,
            "data": _parse_data(data_str) if data_str else datetime.now(),
        })

    logger.info("RSS '%s': %d itens.", fonte["nome"], len(itens))
    return itens


# ── Raspagem HTML ──────────────────────────────────────────────────────────────

def _raspar_html(fonte: dict) -> list[dict]:
    resp = _fazer_request(fonte["url"])
    if not resp:
        return []

    soup     = BeautifulSoup(_decodificar(resp), "html.parser")
    base_url = fonte["base_url"]
    itens  = []
    vistos: set[str] = set()

    cards = soup.select(fonte["seletor_item"])
    if not cards:
        cards = soup.select("article") or soup.select("div.post") or soup.select("li.item")

    for card in cards[:MAX_CARDS]:
        titulo_el = card.select_one(fonte["seletor_titulo"]) or card.select_one("a")
        if not titulo_el:
            continue

        titulo = str(titulo_el.get_text(strip=True))
        if not titulo or len(titulo) < 10:
            continue

        link_el = card.select_one("a[href]") or (titulo_el if titulo_el.name == "a" else None)
        if not link_el:
            continue

        href_val = link_el.get("href")
        if href_val is None:
            href = ""
        else:
            href = str(href_val) if isinstance(href_val, (str, list)) else ""
        if isinstance(href, list):
            href = href[0] if href else ""

        if not href or href == "#":
            continue

        link = urljoin(base_url, href) if href.startswith("/") else href
        if link in vistos:
            continue
        vistos.add(link)

        desc_el  = card.select_one("p, .description, .summary, .excerpt")
        conteudo = str(desc_el.get_text(strip=True)) if desc_el else titulo

        itens.append({
            "titulo": titulo, "link": link, "conteudo": conteudo,
            "data": datetime.now(),
        })

    logger.info("HTML '%s': %d itens.", fonte["nome"], len(itens))
    return itens


# ── Worker por fonte ───────────────────────────────────────────────────────────

def _processar_fonte(fonte: dict) -> list[dict]:
    try:
        if fonte["seletor_item"] is None:
            return _raspar_rss(fonte)
        return _raspar_html(fonte)
    except Exception as exc:
        logger.error("Erro na fonte '%s': %s", fonte["nome"], exc)
        return []


# ── Montagem de Noticia ────────────────────────────────────────────────────────

def _montar_noticia(item: dict, fonte_nome: str) -> Noticia:
    titulo   = item["titulo"]
    conteudo = item["conteudo"]

    categoria = categorizar_noticia(titulo, conteudo)
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
        categoria=categoria,
    )


# ── Função principal ───────────────────────────────────────────────────────────

def buscar_noticias() -> list[Noticia]:
    """
    Raspa todas as fontes em paralelo (ThreadPoolExecutor).
    Tempo esperado: ~10-12s com MAX_WORKERS=4 vs ~40s sequencial.
    """
    todas_raw: list[tuple[dict, str]] = []
    inicio = datetime.now()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futuros = {
            executor.submit(_processar_fonte, fonte): fonte["nome"]
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
        novas.append(_montar_noticia(item, nome_fonte))

    if novas:
        try:
            db.session.add_all(novas)   
            db.session.commit()
            logger.info(f"Sucesso: {len(novas)} notícias salvas.")
        except Exception as exc:
            db.session.rollback()
            logger.error(f"Erro ao salvar: {exc}")

    print(f"\n  Coleta em {duracao}s — {len(novas)} notícias novas")

    return novas
