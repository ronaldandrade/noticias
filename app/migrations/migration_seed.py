# ── Script de seed: cadastra ativos ──────────────────────────────────
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
