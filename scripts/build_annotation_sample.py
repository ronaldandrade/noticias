#!/usr/bin/env python3
"""
scripts/build_annotation_sample.py

Monta o conjunto a anotar:
  - GOLD: notícias que já tinham rótulo humano (arquivo --gold-csv). Entram SEM o
    rótulo humano, para anotação cega e cálculo de concordância.
  - AMOSTRA: sorteio aleatório estratificado por fonte x mês (sem olhar score nem
    palavras-chave, para não herdar viés do baseline lexical).

Antes do sorteio: filtros de encoding/inglês, remoção de duplicatas por URL e por
título normalizado.

Uso:
    python scripts/build_annotation_sample.py --n 1000 --seed 42
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402
from noticias_nlp.data.cleaning import filter_dataset  # noqa: E402


def norm_title(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t).lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()[:80]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw/noticias_raw.parquet")
    ap.add_argument("--gold-csv", default=None, help="CSV com coluna sentimento (rótulo humano)")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data/annotations/a_anotar.parquet")
    a = ap.parse_args()

    raw = pd.read_parquet(ROOT / a.raw)
    df = filter_dataset(raw)
    df["_nt"] = df["titulo"].map(norm_title)
    df = df.drop_duplicates("url").drop_duplicates("_nt").reset_index(drop=True)
    print(f"bruto={len(raw)} limpo+dedup={len(df)}")

    gold_ids: set[int] = set()
    if a.gold_csv:
        g = pd.read_csv(a.gold_csv)
        g = g[g["sentimento"].notna()]
        g["_nt"] = g["titulo"].map(norm_title)
        hum = g.drop_duplicates("_nt").set_index("_nt")["sentimento"]
        gold = df[df["_nt"].isin(hum.index)].copy()
        gold["rotulo_humano"] = gold["_nt"].map(hum)
        gold["conjunto"] = "gold"
        gold_ids = set(gold["id"])
        print(f"gold casado com o banco: {len(gold)}")
    else:
        gold = df.iloc[0:0].copy()

    pool = df[~df["id"].isin(gold_ids)].copy()
    pool["mes"] = pool["data_publicacao"].dt.to_period("M").astype(str)
    pool["estrato"] = pool["fonte"] + "|" + pool["mes"]
    # alocação proporcional ao tamanho do estrato, sorteio aleatório dentro
    frac = a.n / len(pool)
    amostra = (pool.groupby("estrato", group_keys=False)
               .apply(lambda g: g.sample(n=max(1, round(len(g) * frac)), random_state=a.seed)))
    if len(amostra) > a.n:
        amostra = amostra.sample(n=a.n, random_state=a.seed)
    amostra = amostra.copy()
    amostra["conjunto"] = "amostra"

    out = pd.concat([gold, amostra], ignore_index=True)
    out = out.sample(frac=1, random_state=a.seed).reset_index(drop=True)  # embaralha
    cols = ["id", "titulo", "url", "fonte", "data_publicacao", "conjunto", "rotulo_humano"]
    out = out[[c for c in cols if c in out.columns]]
    Path(ROOT / a.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(ROOT / a.out, index=False)
    print(out["conjunto"].value_counts().to_dict(), "->", a.out)
    print(out["fonte"].value_counts().head(8).to_dict())


if __name__ == "__main__":
    main()
