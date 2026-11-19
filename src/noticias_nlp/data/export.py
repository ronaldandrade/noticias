"""
Módulo de exportação de dados brutos da base de notícias.

Lê DATABASE_URL do ambiente de forma segura, extrai a tabela 'Noticia',
computa metadados úteis de pré-auditoria (fonte derivada de URL, contagem de texto)
e salva em formatos binário colunar (Parquet) e tabular comprimido (CSV.gz).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Carrega variáveis de .env se existir localmente, sem sobrescrever ambiente
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def extract_source_from_url(url: str | None) -> str:
    """Extrai o domínio simplificado da fonte a partir da URL."""
    if not url or not isinstance(url, str):
        return "desconhecido"
    try:
        netloc = urlparse(url).netloc.lower()
        if "infomoney.com.br" in netloc:
            return "infomoney"
        if "suno.com.br" in netloc:
            return "suno"
        if "g1.globo.com" in netloc:
            return "g1"
        if "exame.com" in netloc:
            return "exame"
        if "uol.com.br" in netloc:
            return "uol"
        if "livecoins.com.br" in netloc:
            return "livecoins"
        return netloc.replace("www.", "")
    except Exception:
        return "desconhecido"


def get_database_url() -> str:
    """Obtém e normaliza a DATABASE_URL do ambiente."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "DATABASE_URL não configurada no ambiente. "
            "Defina a variável no ambiente ou em um arquivo .env."
        )
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return db_url


def export_database_to_raw(
    output_dir: str | Path = "data/raw",
    chunksize: int = 5000,
    db_url: str | None = None,
) -> dict[str, Any]:
    """
    Exporta a tabela Noticia para Parquet e CSV comprimido em output_dir.

    Retorna um resumo estatístico da exportação.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    if not db_url:
        db_url = get_database_url()

    # Log seguro: dialeto e status sem vazar credenciais/host/senha
    dialect = db_url.split("://")[0] if "://" in db_url else "desconhecido"
    logger.info("Iniciando conexão segura com banco de dados (dialeto: %s)...", dialect)

    engine = create_engine(db_url)
    query = text(
        """
        SELECT
            id,
            titulo,
            conteudo,
            url,
            data_publicacao,
            resumo,
            score_sentimento,
            categoria
        FROM "Noticia"
        ORDER BY data_publicacao ASC, id ASC
        """
    )

    chunks: list[pd.DataFrame] = []
    total_rows = 0

    with engine.connect() as conn:
        logger.info("Executando query e carregando em lotes de %d...", chunksize)
        for chunk in pd.read_sql_query(query, conn, chunksize=chunksize):
            chunks.append(chunk)
            total_rows += len(chunk)
            logger.info("Carregadas %d notícias...", total_rows)

    if not chunks:
        raise RuntimeError("Nenhuma notícia encontrada na tabela 'Noticia'.")

    df = pd.concat(chunks, ignore_index=True)

    # Conversões e enriquecimento de pré-auditoria
    df["data_publicacao"] = pd.to_datetime(df["data_publicacao"])
    df["fonte"] = df["url"].apply(extract_source_from_url)
    df["tamanho_titulo"] = df["titulo"].fillna("").astype(str).str.len()
    df["tamanho_conteudo"] = df["conteudo"].fillna("").astype(str).str.len()
    df["palavras_conteudo"] = df["conteudo"].fillna("").astype(str).str.split().str.len()

    # Métricas de auditoria preliminares
    encoding_ufffd = (
        df["titulo"].fillna("").astype(str).str.contains("\ufffd")
        | df["conteudo"].fillna("").astype(str).str.contains("\ufffd")
    ).sum()

    mojibake_atil = (
        df["titulo"].fillna("").astype(str).str.contains("Ã")
        | df["conteudo"].fillna("").astype(str).str.contains("Ã")
    ).sum()

    vazios_conteudo = (df["conteudo"].isna() | (df["conteudo"].str.strip() == "")).sum()
    duplicatas_url = df.duplicated(subset=["url"]).sum()
    duplicatas_titulo = df.duplicated(subset=["titulo"]).sum()

    # Exportação para Parquet e CSV.gz
    parquet_file = out_path / "noticias_raw.parquet"
    csv_file = out_path / "noticias_raw.csv.gz"

    logger.info("Salvando dataset em Parquet: %s", parquet_file)
    df.to_parquet(parquet_file, index=False, engine="pyarrow", compression="snappy")

    logger.info("Salvando dataset em CSV comprimido: %s", csv_file)
    df.to_csv(csv_file, index=False, compression="gzip")

    parquet_size_mb = parquet_file.stat().st_size / (1024 * 1024)
    csv_size_mb = csv_file.stat().st_size / (1024 * 1024)

    fontes_dist = df["fonte"].value_counts().to_dict()
    categorias_dist = df["categoria"].value_counts(dropna=False).to_dict()

    summary: dict[str, Any] = {
        "total_registros": int(total_rows),
        "data_minima": str(df["data_publicacao"].min()),
        "data_maxima": str(df["data_publicacao"].max()),
        "fontes_distribuicao": fontes_dist,
        "categorias_distribuicao": {str(k): int(v) for k, v in categorias_dist.items()},
        "duplicatas_url": int(duplicatas_url),
        "duplicatas_titulo": int(duplicatas_titulo),
        "conteudos_vazios": int(vazios_conteudo),
        "com_caractere_ufffd": int(encoding_ufffd),
        "com_mojibake_atil": int(mojibake_atil),
        "parquet_path": str(parquet_file),
        "parquet_size_mb": round(parquet_size_mb, 2),
        "csv_path": str(csv_file),
        "csv_size_mb": round(csv_size_mb, 2),
    }

    logger.info("Exportação concluída com sucesso!")
    logger.info(
        "Total: %d registros | Período: %s a %s",
        summary["total_registros"],
        summary["data_minima"],
        summary["data_maxima"],
    )
    logger.info(
        "Arquivos gerados: %s (%.2f MB), %s (%.2f MB)",
        parquet_file.name,
        parquet_size_mb,
        csv_file.name,
        csv_size_mb,
    )

    return summary
