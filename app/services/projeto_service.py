"""
services/projeto_service.py

Números exibidos na página de apresentação do projeto.

- Contagens do corpus: lidas do banco (ao vivo), com fallback se o banco falhar.
- Estatísticas do dataset anotado: lidas de data/labels/rotulos.csv (versionado),
  para que a página nunca diverja dos rótulos publicados.
- Números do processo de construção do dataset (funil e concordância): constantes
  registradas em docs/guia_anotacao.md, calculadas na extração de nov/2026.
"""

import csv
from functools import lru_cache
from pathlib import Path

from .. import db
from ..models import Noticia

ROTULOS_CSV = Path(__file__).resolve().parents[2] / "data" / "labels" / "rotulos.csv"

# Funil de construção do dataset (extração de nov/2026)
FUNIL_BRUTO = 19959
FUNIL_LIMPO = 16433

# Concordância com os rótulos humanos antigos (conjunto "gold", anotação cega)
GOLD_N = 199
GOLD_ACORDO_BINARIO = 89.3
GOLD_KAPPA_BINARIO = 0.76
GOLD_N_BINARIO = 103
GOLD_DISPUTADOS = 11

FONTES = ["G1", "Exame", "InfoMoney", "UOL", "Suno", "Livecoins", "Folha"]

_ORDEM_CLASSES = ["Positivo", "Neutro", "Negativo"]
_NOMES_SPLIT = {"train": "Treino", "val": "Validação", "test": "Teste"}


def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _data_br(iso: str) -> str:
    d = iso[:10].split("-")
    return f"{d[2]}/{d[1]}/{d[0]}" if len(d) == 3 else iso


@lru_cache(maxsize=1)
def _dataset() -> dict | None:
    try:
        with open(ROTULOS_CSV, newline="", encoding="utf-8") as f:
            linhas = list(csv.DictReader(f))
    except OSError:
        return None
    if not linhas:
        return None

    total = len(linhas)
    contagem: dict[str, int] = {}
    for r in linhas:
        contagem[r["rotulo"]] = contagem.get(r["rotulo"], 0) + 1
    classes = [
        {"nome": c, "n": contagem.get(c, 0), "pct": round(100 * contagem.get(c, 0) / total, 1)}
        for c in _ORDEM_CLASSES
    ]

    splits = []
    for chave in ("train", "val", "test"):
        grupo = [r for r in linhas if r["split"] == chave]
        if not grupo:
            continue
        datas = sorted(r["data_publicacao"] for r in grupo)
        splits.append({
            "nome": _NOMES_SPLIT[chave],
            "n": len(grupo),
            "pct": round(100 * len(grupo) / total, 1),
            "ini": _data_br(datas[0]),
            "fim": _data_br(datas[-1]),
        })

    return {"n": total, "classes": classes, "splits": splits}


def _corpus() -> dict:
    """Total e período do corpus, ao vivo. Falha de banco não derruba a página."""
    try:
        total = Noticia.query.count()
        ini, fim = db.session.query(
            db.func.min(Noticia.data_publicacao), db.func.max(Noticia.data_publicacao)
        ).one()
        return {
            "total": total,
            "total_fmt": fmt_int(total),
            "ini": ini.strftime("%m/%Y") if ini else None,
            "fim": fim.strftime("%m/%Y") if fim else None,
        }
    except Exception:
        db.session.rollback()
        return {"total": None, "total_fmt": "—", "ini": None, "fim": None}


def stats_projeto() -> dict:
    return {
        "corpus": _corpus(),
        "dataset": _dataset(),
        "dataset_n_fmt": fmt_int(_dataset()["n"]) if _dataset() else "—",
        "funil": {
            "bruto": FUNIL_BRUTO,
            "bruto_fmt": fmt_int(FUNIL_BRUTO),
            "limpo": FUNIL_LIMPO,
            "limpo_fmt": fmt_int(FUNIL_LIMPO),
            "limpo_pct": round(100 * FUNIL_LIMPO / FUNIL_BRUTO),
            "anotado_pct": max(
                3, round(100 * (_dataset()["n"] if _dataset() else 0) / FUNIL_BRUTO)
            ),
        },
        "gold": {
            "n": GOLD_N,
            "n_binario": GOLD_N_BINARIO,
            "acordo": str(GOLD_ACORDO_BINARIO).replace(".", ","),
            "kappa": str(GOLD_KAPPA_BINARIO).replace(".", ","),
            "disputados": GOLD_DISPUTADOS,
        },
        "fontes": FONTES,
    }
