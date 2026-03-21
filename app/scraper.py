import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from .models import Noticia
from . import db
from .services.resume_text_service import resumir_texto

logger = logging.getLogger(__name__)

# Timeout padrão para requisições (segundos)
REQUEST_TIMEOUT = 10

# Headers para evitar bloqueios por user-agent
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NewsBot/1.0; +https://seusite.com/bot)"
    )
}

# ── Fontes RSS ────────────────────────────────────────────────────────────────
# Cada entrada: (nome_exibição, url_rss, num_frases_resumo)
FONTES_RSS = [
    # ── Brasil ────────────────────────────────────────────────────────────────
    ("G1 Economia",          "https://g1.globo.com/rss/g1/economia/",                          2),
    ("Exame",                "https://exame.com/feed/",                                         2),
    ("InfoMoney",            "https://www.infomoney.com.br/feed/",                              2),
    ("Valor Econômico",      "https://valor.globo.com/rss/financas/",                           2),
    ("Investing.com BR",     "https://br.investing.com/rss/news.rss",                           2),
    ("Monitor do Mercado",   "https://monitordosmercados.com.br/feed/",                         2),
    ("Suno Research",        "https://www.sunoresearch.com.br/feed/",                           2),
    ("Finanças UOL",         "https://rss.uol.com.br/feed/economia.xml",                        2),
    ("Agência Brasil Econ.", "https://agenciabrasil.ebc.com.br/economia/feed",                  2),
    ("CNN Brasil Negócios",  "https://www.cnnbrasil.com.br/economia/negocios/feed/",            2),
    ("CNN Brasil Finanças",  "https://www.cnnbrasil.com.br/economia/financas/feed/",            2),

    # ── Internacional ─────────────────────────────────────────────────────────
    ("Reuters Business",     "https://feeds.reuters.com/reuters/businessNews",                  2),
    ("Reuters Markets",      "https://feeds.reuters.com/reuters/marketsNews",                   2),
    ("MarketWatch",          "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines", 2),
    ("Seeking Alpha",        "https://seekingalpha.com/feed.xml",                               2),
    ("Yahoo Finance",        "https://finance.yahoo.com/news/rssindex",                         2),
    ("Bloomberg Markets",    "https://feeds.bloomberg.com/markets/news.rss",                    2),
    ("CNBC Finance",         "https://www.cnbc.com/id/10000664/device/rss/rss.html",            2),
    ("Investing.com",        "https://www.investing.com/rss/news.rss",                          2),
    ("FT Markets",           "https://www.ft.com/rss/home/markets",                             2),
]


def _parse_data(data_str: str) -> datetime:
    """Tenta converter a string de data em diversos formatos comuns em RSS."""
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
    """Extrai texto de uma tag BeautifulSoup, removendo HTML interno se houver."""
    if tag is None:
        return ""
    texto = tag.get_text(strip=True)
    # Às vezes description vem com HTML escapado — parse novamente
    if "<" in texto:
        texto = BeautifulSoup(texto, "html.parser").get_text(strip=True)
    return texto or "Sem descrição"


def _raspar_fonte(nome: str, url: str, num_frases: int) -> list[Noticia]:
    """Raspa um único feed RSS e retorna lista de objetos Noticia (sem salvar)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        resp.encoding = "utf-8"
    except requests.RequestException as exc:
        logger.warning("Falha ao buscar '%s' (%s): %s", nome, url, exc)
        return []

    try:
        soup = BeautifulSoup(resp.text, "xml", from_encoding="utf-8")
    except Exception as exc:
        logger.warning("Falha ao parsear XML de '%s': %s", nome, exc)
        return []

    noticias = []
    for item in soup.find_all("item"):
        titulo_tag  = item.find("title")
        link_tag    = item.find("link")
        desc_tag    = item.find("description")
        data_tag    = item.find("pubDate") or item.find("dc:date")

        if not titulo_tag or not link_tag:
            continue  # item inválido

        titulo   = _texto_limpo(titulo_tag)
        link     = link_tag.get_text(strip=True)
        conteudo = _texto_limpo(desc_tag)
        data_str = data_tag.get_text(strip=True) if data_tag else ""
        data     = _parse_data(data_str) if data_str else datetime.now()

        try:
            resumo = resumir_texto(conteudo, num_frases=num_frases)
        except Exception as exc:
            logger.warning("Erro ao resumir notícia '%s': %s", titulo[:60], exc)
            resumo = conteudo[:200]

        noticias.append(
            Noticia(
                titulo=titulo,
                conteudo=conteudo,
                url=link,
                # fonte=nome,
                data_publicacao=data,
                resumo=resumo,
            )
        )

    logger.info("'%s': %d notícias encontradas.", nome, len(noticias))
    return noticias


def buscar_noticias() -> list[Noticia]:
    """
    Raspa todas as fontes configuradas em FONTES_RSS, persiste novas notícias
    no banco de dados e retorna a lista completa encontrada nesta execução.
    """
    todas: list[Noticia] = []

    for nome, url, num_frases in FONTES_RSS:
        todas.extend(_raspar_fonte(nome, url, num_frases))

    # Deduplicação em memória (mesma execução) antes de consultar o banco
    urls_vistas: set[str] = set()
    novas: list[Noticia] = []

    for noticia in todas:
        if noticia.url in urls_vistas:
            continue
        urls_vistas.add(noticia.url)

        # Deduplicação contra o banco de dados
        if not Noticia.query.filter_by(url=noticia.url).first():
            novas.append(noticia)

    if novas:
        try:
            db.session.bulk_save_objects(novas)
            db.session.commit()
            logger.info("Salvas %d novas notícias no banco.", len(novas))
        except Exception as exc:
            db.session.rollback()
            logger.error("Erro ao salvar notícias: %s", exc)
            raise

    return todas