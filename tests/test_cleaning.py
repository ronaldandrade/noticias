"""
Testes unitários para o módulo de limpeza e filtragem de notícias.
"""

import pandas as pd
from noticias_nlp.data.cleaning import (
    has_encoding_error,
    is_uol_with_encoding_error,
    is_english_text,
    is_english_news,
    filter_dataset,
)


def test_has_encoding_error():
    assert has_encoding_error("Bolsa tem queda e d\ufffdlar fecha em alta") is True
    assert has_encoding_error("Preço de ações da Petrobras sobe hoje") is False
    assert has_encoding_error(None) is False
    assert has_encoding_error("") is False


def test_is_uol_with_encoding_error():
    bad_uol = {
        "fonte": "uol",
        "titulo": "Bolsa tem queda e d\ufffdlar fecha em alta, a R$ 5,30, maior cota\ufffdo",
        "conteudo": "Texto de teste",
    }
    good_uol = {
        "fonte": "uol",
        "titulo": "Bolsa tem alta e dólar fecha em queda nesta terça-feira",
        "conteudo": "Texto limpo",
    }
    other_source_bad = {
        "fonte": "exame",
        "titulo": "Bolsa tem queda e d\ufffdlar fecha em alta",
        "conteudo": "Texto limpo",
    }
    assert is_uol_with_encoding_error(bad_uol) is True
    assert is_uol_with_encoding_error(good_uol) is False
    assert is_uol_with_encoding_error(other_source_bad) is False


def test_is_english_text():
    assert is_english_text("The Federal Reserve decided to hold interest rates steady") is True
    assert is_english_text("O Banco Central do Brasil manteve a taxa de juros Selic") is False
    assert is_english_text(None) is False
    assert is_english_text("") is False


def test_is_english_news():
    en_news_domain = {
        "fonte": "bloomberg.com",
        "titulo": "Global markets react to inflation report",
    }
    en_news_text = {
        "fonte": "exame",
        "titulo": "Tech stocks rally as quarterly earnings top Wall Street forecasts",
    }
    pt_news = {
        "fonte": "infomoney",
        "titulo": "Ibovespa bate recorde histórico com entrada de capital estrangeiro",
    }
    assert is_english_news(en_news_domain) is True
    assert is_english_news(en_news_text) is True
    assert is_english_news(pt_news) is False


def test_filter_dataset_excludes_bad_uol_and_english():
    df = pd.DataFrame([
        {
            "id": 1,
            "fonte": "uol",
            "titulo": "D\ufffdlar sobe com avers\ufffdo ao risco",
            "conteudo": "texto",
        },
        {
            "id": 2,
            "fonte": "uol",
            "titulo": "Dólar sobe com aversão ao risco",
            "conteudo": "texto limpo e sem problemas",
        },
        {
            "id": 3,
            "fonte": "nytimes.com",
            "titulo": "Federal Reserve signals future rate adjustments",
            "conteudo": "content in english",
        },
        {
            "id": 4,
            "fonte": "infomoney",
            "titulo": "Petrobras anuncia pagamento bilionário de dividendos",
            "conteudo": "conteúdo em português",
        },
    ])

    df_filtered = filter_dataset(df, drop_uol_encoding_errors=True, drop_english=True)
    ids_restantes = df_filtered["id"].tolist()

    # O id 1 (uol corrompido) e o id 3 (inglês) devem ser excluídos
    assert 1 not in ids_restantes
    assert 3 not in ids_restantes
    # O id 2 (uol íntegro) e o id 4 (infomoney em pt) devem ser mantidos
    assert 2 in ids_restantes
    assert 4 in ids_restantes
