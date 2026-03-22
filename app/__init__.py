from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config') 

    db.init_app(app)
    migrate.init_app(app, db)

    # Importa e registra as rotas depois de configurado
    from .routes import bp as routes_bp, admin_bp, relatorio_bp
    app.register_blueprint(routes_bp)
    app.register_blueprint(admin_bp)     # Registra as rotas de admin (/admin)
    app.register_blueprint(relatorio_bp) # Registra as rotas de relatório (/relatorio)

    with app.app_context():
        db.create_all()

    return app

app = create_app()