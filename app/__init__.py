from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail

db           = SQLAlchemy()
migrate      = Migrate()
login_manager = LoginManager()
bcrypt       = Bcrypt()
limiter      = Limiter(key_func=get_remote_address)
mail         = Mail()


def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    limiter.init_app(app)
    mail.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faça login para acessar esta página."
    login_manager.login_message_category = "info"

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprints existentes
    from .routes import bp as routes_bp, admin_bp, relatorio_bp, termometro_bp
    from .auth import auth_bp

    # Novos blueprints SaaS
    from .billing import billing_bp
    from .account import account_bp
    from .api import api_bp

    app.register_blueprint(routes_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(relatorio_bp)
    app.register_blueprint(termometro_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(api_bp)

    from .cli import pipeline
    app.cli.add_command(pipeline)

    # Seed de planos ao iniciar (idempotente)
    with app.app_context():
        _seed_plans()

    return app


def _seed_plans():
    """Garante que os planos base existam no banco. Idempotente."""
    from .models import Plan
    from sqlalchemy import inspect
    from sqlalchemy.exc import OperationalError

    # Tabela pode não existir ainda (antes da primeira migração)
    try:
        inspector = inspect(db.engine)
        if 'plan' not in inspector.get_table_names():
            return
    except OperationalError:
        return

    planos = [
        dict(
            nome="free",
            display_nome="Grátis",
            preco_mensal=0.0,
            max_ativos=5,
            historico_dias=7,
            acesso_api=False,
            acesso_relatorio=False,
            acesso_termometro=False,
            acesso_dashboard=True,
        ),
        dict(
            nome="pro",
            display_nome="Pro",
            preco_mensal=49.90,
            max_ativos=-1,
            historico_dias=90,
            acesso_api=True,
            acesso_relatorio=True,
            acesso_termometro=True,
            acesso_dashboard=True,
        ),
        dict(
            nome="enterprise",
            display_nome="Enterprise",
            preco_mensal=199.90,
            max_ativos=-1,
            historico_dias=365,
            acesso_api=True,
            acesso_relatorio=True,
            acesso_termometro=True,
            acesso_dashboard=True,
        ),
    ]

    for dados in planos:
        if not Plan.query.filter_by(nome=dados["nome"]).first():
            db.session.add(Plan(**dados))

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
