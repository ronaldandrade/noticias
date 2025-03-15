class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///noticias.db'  # Banco SQLite simples
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = True