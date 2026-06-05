"""add user_favorite_asset table

Revision ID: d1acb17822eb
Revises: a1b2c3d4e5f6
Create Date: 2026-06-05 00:45:37.409971

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1acb17822eb'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_favorite_asset',
        sa.Column('id',       sa.Integer(),      nullable=False),
        sa.Column('user_id',  sa.Integer(),      nullable=False),
        sa.Column('symbol',   sa.String(20),     nullable=False),
        sa.Column('nome',     sa.String(100),    nullable=True),
        sa.Column('added_at', sa.DateTime(),     nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'symbol', name='uq_user_favorite_symbol'),
    )


def downgrade():
    op.drop_table('user_favorite_asset')
