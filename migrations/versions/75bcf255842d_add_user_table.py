"""add user table

Revision ID: 75bcf255842d
Revises: 592a5ee3cac2
Create Date: 2026-06-04 00:22:35.560763

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '75bcf255842d'
down_revision = '592a5ee3cac2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=150), nullable=False),
    sa.Column('password_hash', sa.String(length=256), nullable=False),
    sa.Column('nome', sa.String(length=100), nullable=True),
    sa.Column('criado_em', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )


def downgrade():
    op.drop_table('user')
