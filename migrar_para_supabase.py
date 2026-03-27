"""
migrar_para_supabase.py

Copia todos os dados do SQLite local para o Supabase (PostgreSQL).
Rode UMA VEZ, com DATABASE_URL apontando para o Supabase.

    export DATABASE_URL="postgresql://postgres:SENHA@db.xxx.supabase.co:5432/postgres"
    python migrar_para_supabase.py

Ordem de migração respeita as FK:
  1. Ativo
  2. Noticia
  3. Cotacao
  4. Correlacao
"""

import os
import sqlite3
from datetime import datetime

# ── Conexão com SQLite ────────────────────────────────────────────────────────
SQLITE_PATH = "instance/noticias.db"  # ajuste se o seu .db estiver em outro lugar

if not os.path.exists(SQLITE_PATH):
    # Tenta caminhos alternativos comuns
    for caminho in ["noticias.db", "app/noticias.db", "instance/noticias.db"]:
        if os.path.exists(caminho):
            SQLITE_PATH = caminho
            break
    else:
        raise FileNotFoundError(
            f"Banco SQLite não encontrado. Ajuste SQLITE_PATH no script. "
            f"Tentados: instance/noticias.db, noticias.db, app/noticias.db"
        )

print(f"SQLite encontrado em: {SQLITE_PATH}")

# ── Conexão com Supabase via SQLAlchemy ───────────────────────────────────────
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise EnvironmentError(
        "DATABASE_URL não encontrada. "
        "Execute: export DATABASE_URL='postgresql://...'"
    )

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

from app import create_app, db
from app.models import Ativo, Noticia, Cotacao, Correlacao

app = create_app()


def migrar():
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    cur = sqlite_conn.cursor()

    with app.app_context():

        # ── 1. Ativos ─────────────────────────────────────────────────────────
        cur.execute("SELECT * FROM ativo")
        ativos_sqlite = cur.fetchall()
        print(f"\n[1/4] Migrando {len(ativos_sqlite)} ativos...")

        ativos_migrados = 0
        for row in ativos_sqlite:
            if not Ativo.query.filter_by(ticker=row["ticker"]).first():
                db.session.add(Ativo(
                    id=row["id"],
                    ticker=row["ticker"],
                    nome=row["nome"],
                    setor=row["setor"] if "setor" in row.keys() else None,
                ))
                ativos_migrados += 1

        db.session.commit()
        print(f"    {ativos_migrados} ativos inseridos, "
              f"{len(ativos_sqlite) - ativos_migrados} já existiam.")

        # ── 2. Notícias ───────────────────────────────────────────────────────
        cur.execute("SELECT COUNT(*) FROM noticia")
        total_noticias = cur.fetchone()[0]
        print(f"\n[2/4] Migrando {total_noticias} notícias (em lotes de 500)...")

        noticias_migradas = 0
        offset = 0
        lote   = 500

        while True:
            cur.execute(f"SELECT * FROM noticia LIMIT {lote} OFFSET {offset}")
            rows = cur.fetchall()
            if not rows:
                break

            urls_existentes = {
                n.url for n in db.session.query(Noticia.url).filter(
                    Noticia.url.in_([r["url"] for r in rows])
                ).all()
            }

            novas = []
            for row in rows:
                if row["url"] in urls_existentes:
                    continue

                # Converte data string para datetime se necessário
                data_pub = row["data_publicacao"]
                if isinstance(data_pub, str):
                    try:
                        data_pub = datetime.fromisoformat(data_pub)
                    except ValueError:
                        data_pub = datetime.now()

                colunas = [c[0] for c in cur.description]

                novas.append(Noticia(
                    id=row["id"],
                    titulo=row["titulo"],
                    conteudo=row["conteudo"],
                    url=row["url"],
                    resumo=row["resumo"] if "resumo" in colunas else None,
                    score_sentimento=row["score_sentimento"] if "score_sentimento" in colunas else None,
                    ativo_id=row["ativo_id"] if "ativo_id" in colunas else None,
                    data_publicacao=data_pub,
                ))

            if novas:
                db.session.bulk_save_objects(novas)
                db.session.commit()
                noticias_migradas += len(novas)

            offset += lote
            print(f"    {min(offset, total_noticias)}/{total_noticias} processadas...", end="\r")

        print(f"\n    {noticias_migradas} notícias inseridas.")

        # ── 3. Cotações ───────────────────────────────────────────────────────
        cur.execute("SELECT COUNT(*) FROM cotacao")
        total_cotacoes = cur.fetchone()[0]
        print(f"\n[3/4] Migrando {total_cotacoes} cotações...")

        cotacoes_migradas = 0
        offset = 0

        while True:
            cur.execute(f"SELECT * FROM cotacao LIMIT {lote} OFFSET {offset}")
            rows = cur.fetchall()
            if not rows:
                break

            novas = []
            for row in rows:
                existe = Cotacao.query.filter_by(
                    ativo_id=row["ativo_id"],
                    data=row["data"]
                ).first()
                if existe:
                    continue

                data_cot = row["data"]
                if isinstance(data_cot, str):
                    try:
                        from datetime import date
                        data_cot = date.fromisoformat(data_cot)
                    except ValueError:
                        continue

                colunas = [c[0] for c in cur.description]
                novas.append(Cotacao(
                    id=row["id"],
                    ativo_id=row["ativo_id"],
                    data=data_cot,
                    preco_fechamento=row["preco_fechamento"],
                    preco_abertura=row["preco_abertura"] if "preco_abertura" in colunas else None,
                    variacao_pct=row["variacao_pct"] if "variacao_pct" in colunas else None,
                    volume=row["volume"] if "volume" in colunas else None,
                ))

            if novas:
                db.session.bulk_save_objects(novas)
                db.session.commit()
                cotacoes_migradas += len(novas)

            offset += lote

        print(f"    {cotacoes_migradas} cotações inseridas.")

        # ── 4. Correlações ────────────────────────────────────────────────────
        try:
            cur.execute("SELECT * FROM correlacao")
            correlacoes_sqlite = cur.fetchall()
            print(f"\n[4/4] Migrando {len(correlacoes_sqlite)} correlações...")

            correlacoes_migradas = 0
            colunas = [c[0] for c in cur.description]

            for row in correlacoes_sqlite:
                novas_corr = []
                data_i = row["data_inicio"]
                data_f = row["data_fim"]
                if isinstance(data_i, str):
                    from datetime import date
                    data_i = date.fromisoformat(data_i)
                    data_f = date.fromisoformat(data_f)

                existe = Correlacao.query.filter_by(
                    ativo_id=row["ativo_id"],
                    data_inicio=data_i,
                    data_fim=data_f,
                ).first()
                if existe:
                    continue

                criado_em = row["criado_em"] if "criado_em" in colunas else datetime.now()
                if isinstance(criado_em, str):
                    try:
                        criado_em = datetime.fromisoformat(criado_em)
                    except ValueError:
                        criado_em = datetime.now()

                novas_corr.append(Correlacao(
                    ativo_id=row["ativo_id"],
                    data_inicio=data_i,
                    data_fim=data_f,
                    pearson=row["pearson"] if "pearson" in colunas else None,
                    spearman=row["spearman"] if "spearman" in colunas else None,
                    n_noticias=row["n_noticias"] if "n_noticias" in colunas else None,
                    criado_em=criado_em,
                ))
                correlacoes_migradas += 1

            if novas_corr:
                db.session.bulk_save_objects(novas_corr)
                db.session.commit()

            print(f"    {correlacoes_migradas} correlações inseridas.")

        except sqlite3.OperationalError:
            print("    Tabela correlacao não encontrada — pulando.")

        # ── Resumo ────────────────────────────────────────────────────────────
        print("\n" + "─" * 50)
        print("Migração concluída!")
        print(f"  Ativos:      {Ativo.query.count()}")
        print(f"  Notícias:    {Noticia.query.count()}")
        print(f"  Cotações:    {Cotacao.query.count()}")
        print(f"  Correlações: {Correlacao.query.count()}")
        print("─" * 50)

    sqlite_conn.close()


if __name__ == "__main__":
    migrar()
