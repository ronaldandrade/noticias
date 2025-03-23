import os

class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///noticias.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = True
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    SECRET_KEY = os.getenv('SECRET_KEY', 'uma-chave-secreta-super-foda')  # Default pra local