"""Migration manual — rode via Flask-Migrate ou copie os comandos SQL

Se você usa Flask-Migrate (flask db migrate / upgrade), basta adicionar
os novos models ao models.py e rodar:

    flask db migrate -m "adiciona ativo cotacao correlacao e score_sentimento"
    flask db upgrade

Caso prefira rodar o SQL diretamente (SQLite / PostgreSQL):
"""

# ── SQL equivalente (referência) ──────────────────────────────────────────────
SQL = """
-- Tabela de ativos monitorados
CREATE TABLE IF NOT EXISTS ativo (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker VARCHAR(20)  NOT NULL UNIQUE,
    nome   VARCHAR(100) NOT NULL,
    setor  VARCHAR(100)
);

-- Cotações diárias
CREATE TABLE IF NOT EXISTS cotacao (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo_id         INTEGER NOT NULL REFERENCES ativo(id),
    data             DATE    NOT NULL,
    preco_fechamento FLOAT   NOT NULL,
    preco_abertura   FLOAT,
    variacao_pct     FLOAT,
    volume           BIGINT,
    UNIQUE (ativo_id, data)
);

-- Resultados de correlação por período
CREATE TABLE IF NOT EXISTS correlacao (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo_id    INTEGER NOT NULL REFERENCES ativo(id),
    data_inicio DATE    NOT NULL,
    data_fim    DATE    NOT NULL,
    pearson     FLOAT,
    spearman    FLOAT,
    n_noticias  INTEGER,
    criado_em   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Novos campos na tabela noticia existente
ALTER TABLE noticia ADD COLUMN score_sentimento FLOAT;
ALTER TABLE noticia ADD COLUMN ativo_id INTEGER REFERENCES ativo(id);
ALTER TABLE noticia ADD COLUMN fonte VARCHAR(100);
"""

# ── Script de seed: cadastra ativos iniciais ──────────────────────────────────
ATIVOS_INICIAIS = [
    # (ticker yfinance,  nome de exibição,        setor)
    ("PETR4.SA", "Petrobras PN",        "Energia"),
    ("VALE3.SA", "Vale ON",             "Mineração"),
    ("ITUB4.SA", "Itaú Unibanco PN",   "Financeiro"),
    ("BBDC4.SA", "Bradesco PN",         "Financeiro"),
    ("MGLU3.SA", "Magazine Luiza ON",   "Varejo"),
    ("BTC-USD",  "Bitcoin",             "Cripto"),
    ("^BVSP",    "Ibovespa",            "Índice"),
]


def seed_ativos(app):
    """
    Chame esta função UMA VEZ para popular a tabela ativo.

    Exemplo no seu create_app() ou em um script separado:
        from app.migrations_seed import seed_ativos
        seed_ativos(app)
    """
    from app.models import Ativo
    from app import db

    with app.app_context():
        for ticker, nome, setor in ATIVOS_INICIAIS:
            if not Ativo.query.filter_by(ticker=ticker).first():
                db.session.add(Ativo(ticker=ticker, nome=nome, setor=setor))
        db.session.commit()
        print("Ativos cadastrados com sucesso.")


if __name__ == "__main__":
    print(SQL)