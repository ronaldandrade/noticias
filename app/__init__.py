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

    from .routes import bp as routes_bp, admin_bp, relatorio_bp
    app.register_blueprint(routes_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(relatorio_bp)

    from .cli import pipeline
    app.cli.add_command(pipeline)

    return app
