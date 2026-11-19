"""remove tabelas do SaaS (usuários, planos, billing, api keys, favoritos)

Revision ID: e7f1c2a9b3d4
Revises: d1acb17822eb
Create Date: 2026-11-18

"""
from alembic import op
import sqlalchemy as sa


revision = 'e7f1c2a9b3d4'
down_revision = 'd1acb17822eb'
branch_labels = None
depends_on = None

# Ordem importa: filhas (com FK para user/plan) antes das mães.
TABELAS_SAAS = [
    'user_favorite_asset',
    'password_reset_token',
    'api_key',
    'subscription',
    'plan',
    'user',
]


def upgrade():
    existentes = set(sa.inspect(op.get_bind()).get_table_names())
    for tabela in TABELAS_SAAS:
        if tabela in existentes:
            op.drop_table(tabela)


def downgrade():
    raise NotImplementedError(
        "As tabelas do SaaS foram removidas de propósito; não há downgrade."
    )
