"""
Módulo de limpeza e filtragem de notícias.

Implementa regras de negócio para:
1. Excluir notícias com erro de encoding (em especial feeds do UOL corrompidos com caractere de substituição \ufffd ou mojibake).
2. Excluir notícias em língua inglesa (fontes estrangeiras e conteúdos em inglês).
3. Filtrar notícias com conteúdo íntegro para classificação e benchmark.
"""

from __future__ import annotations

import re
from typing import Set
import pandas as pd

# Fontes primariamente em inglês
ENGLISH_SOURCES: Set[str] = {
    "nytimes.com",
    "finance.yahoo.com",
    "seekingalpha.com",
    "bloomberg.com",
    "cnbc.com",
    "marketwatch.com",
    "investors.com",
    "barrons.com",
    "wsj.com",
    "reuters.com",
    "ft.com",
}

# Stopwords mínimas para discriminação PT vs EN
STOPWORDS_EN: Set[str] = {
    "the", "and", "to", "of", "a", "in", "is", "that", "for",
    "it", "as", "was", "with", "on", "at", "by", "from", "up",
    "about", "into", "over", "after", "says", "market", "stocks"
}

STOPWORDS_PT: Set[str] = {
    "o", "a", "os", "as", "um", "uma", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "para", "com", "por", "que",
    "se", "ao", "aos", "mais", "não", "como", "mas", "foi", "sobre"
}


def has_encoding_error(text: str | None) -> bool:
    """Detecta se uma string contém caracteres corrompidos ou mojibake."""
    if not text or not isinstance(text, str):
        return False
    # Caractere de substituição Unicode padrão para decodificação falha
    if "\ufffd" in text:
        return True
    # Mojibakes comuns decorrentes de ISO-8859-1 lido como UTF-8
    mojibake_patterns = [r"Ã§", r"Ã£", r"Ã©", r"Ã³", r"Ãª", r"â€™", r"â€œ", r"â€"]
    for pat in mojibake_patterns:
        if re.search(pat, text):
            return True
    return False


def is_uol_with_encoding_error(row: pd.Series | dict) -> bool:
    """Verifica se a notícia é do UOL e contém erro de encoding no título ou conteúdo."""
    fonte = str(row.get("fonte", "")).lower()
    if "uol" not in fonte:
        return False
    titulo = str(row.get("titulo", ""))
    conteudo = str(row.get("conteudo", ""))
    return has_encoding_error(titulo) or has_encoding_error(conteudo)


def is_english_text(text: str | None) -> bool:
    """Classifica se um texto está em inglês baseado em ocorrência relativa de stopwords."""
    if not text or not isinstance(text, str) or not text.strip():
        return False
    words = set(re.findall(r"\b[a-záàâãéèêíïóôõöúçñ]{2,}\b", text.lower()))
    en_count = len(words & STOPWORDS_EN)
    pt_count = len(words & STOPWORDS_PT)
    return (en_count > pt_count) and (en_count >= 2)


def is_english_news(row: pd.Series | dict) -> bool:
    """Verifica se uma notícia é em inglês, seja por domínio de origem ou pelo título."""
    fonte = str(row.get("fonte", "")).lower()
    if fonte in ENGLISH_SOURCES:
        return True
    titulo = str(row.get("titulo", ""))
    return is_english_text(titulo)


def filter_dataset(
    df: pd.DataFrame,
    drop_uol_encoding_errors: bool = True,
    drop_english: bool = True,
    min_title_length: int = 15,
) -> pd.DataFrame:
    """
    Aplica filtros de qualidade e limpeza no DataFrame de notícias.
    
    Args:
        df: DataFrame original com colunas titulo, conteudo, fonte.
        drop_uol_encoding_errors: Se True, remove notícias do UOL com erro de encoding.
        drop_english: Se True, remove notícias em inglês.
        min_title_length: Comprimento mínimo aceitável de título.
        
    Returns:
        DataFrame limpo e filtrado.
    """
    df_clean = df.copy()

    # 1. Filtro de erro de encoding no UOL
    if drop_uol_encoding_errors:
        uol_bad_mask = df_clean.apply(is_uol_with_encoding_error, axis=1)
        df_clean = df_clean[~uol_bad_mask]

    # 2. Filtro de notícias em inglês
    if drop_english:
        english_mask = df_clean.apply(is_english_news, axis=1)
        df_clean = df_clean[~english_mask]

    # 3. Filtro de tamanho mínimo de título
    if min_title_length > 0 and "titulo" in df_clean.columns:
        valid_title = df_clean["titulo"].fillna("").astype(str).str.strip().str.len() >= min_title_length
        df_clean = df_clean[valid_title]

    return df_clean.reset_index(drop=True)
