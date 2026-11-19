"""remove ativos, cotações e correlações (e Noticia.ativo_id)

Revision ID: f3a9d2b7c1e8
Revises: e7f1c2a9b3d4
Create Date: 2026-11-18

"""
from alembic import op
import sqlalchemy as sa


revision = 'f3a9d2b7c1e8'
down_revision = 'e7f1c2a9b3d4'
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())

    if 'ativo_id' in {c['name'] for c in insp.get_columns('Noticia')}:
        for fk in insp.get_foreign_keys('Noticia'):
            if fk['constrained_columns'] == ['ativo_id'] and fk.get('name'):
                op.drop_constraint(fk['name'], 'Noticia', type_='foreignkey')
        op.drop_column('Noticia', 'ativo_id')

    existentes = set(insp.get_table_names())
    # filhas antes da mãe
    for tabela in ('cotacao', 'correlacao', 'ativo'):
        if tabela in existentes:
            op.drop_table(tabela)


def downgrade():
    raise NotImplementedError(
        "Ativos, cotações e correlações foram removidos de propósito; "
        "backup em CSV em ~/backup_ativos."
    )
