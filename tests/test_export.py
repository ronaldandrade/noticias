"""
Testes unitários para o módulo de exportação e extração de dados.
"""

from noticias_nlp.data.export import extract_source_from_url


def test_extract_source_from_url_known_domains():
    assert extract_source_from_url("https://www.infomoney.com.br/mercados/artigo-1") == "infomoney"
    assert extract_source_from_url("https://suno.com.br/acoes/petr4/") == "suno"
    assert extract_source_from_url("https://g1.globo.com/economia/noticia.ghtml") == "g1"
    assert extract_source_from_url("https://exame.com/economia/materia-1") == "exame"
    assert extract_source_from_url("https://noticias.uol.com.br/economia/x.htm") == "uol"
    assert extract_source_from_url("https://livecoins.com.br/bitcoin-hoje") == "livecoins"


def test_extract_source_from_url_fallback():
    assert extract_source_from_url("https://bloomberg.com/news/article") == "bloomberg.com"
    assert extract_source_from_url(None) == "desconhecido"
    assert extract_source_from_url("") == "desconhecido"
