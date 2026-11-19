#!/usr/bin/env python3
"""
scripts/export_raw_data.py

Script CLI para extrair os dados da base relacional (PostgreSQL Supabase)
para data/raw/noticias_raw.parquet e data/raw/noticias_raw.csv.gz.

Uso:
    python scripts/export_raw_data.py [--output-dir data/raw]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Adiciona src ao path para execução direta
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from noticias_nlp.data.export import export_database_to_raw  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exporta tabela Noticia da base relacional para Parquet e CSV."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/raw",
        help="Diretório de saída (default: data/raw)",
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=5000,
        help="Tamanho do lote para leitura (default: 5000)",
    )
    args = parser.parse_args()

    try:
        summary = export_database_to_raw(
            output_dir=args.output_dir, chunksize=args.chunksize
        )
        print("\n" + "=" * 60)
        print("RESUMO DA EXPORTAÇÃO (Fase 0)")
        print("=" * 60)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"\n[ERRO NA EXPORTAÇÃO] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
