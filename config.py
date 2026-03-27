import os

class Config:
    # Usa DATABASE_URL do ambiente se existir (produção com Supabase)
    # Caso contrário, usa SQLite local (desenvolvimento)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///noticias.db"
    )

    # Supabase retorna URLs com prefixo "postgres://" (antigo)
    # SQLAlchemy 2.x exige "postgresql://" — corrige automaticamente
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql://", 1
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"