"""saas infrastructure: plans, subscriptions, api_keys, password_reset_tokens, user fields

Revision ID: a1b2c3d4e5f6
Revises: 75bcf255842d
Create Date: 2026-06-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '75bcf255842d'
branch_labels = None
depends_on = None


def upgrade():
    # ── Novos campos na tabela user ───────────────────────────────────────────
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', sa.String(length=20), nullable=False, server_default='user'))
        batch_op.add_column(sa.Column('email_verificado', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('stripe_customer_id', sa.String(length=100), nullable=True))

    # ── Planos ────────────────────────────────────────────────────────────────
    op.create_table(
        'plan',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=50), nullable=False),
        sa.Column('display_nome', sa.String(length=100), nullable=False),
        sa.Column('preco_mensal', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('stripe_price_id', sa.String(length=100), nullable=True),
        sa.Column('max_ativos', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('historico_dias', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('acesso_api', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('acesso_relatorio', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('acesso_termometro', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('acesso_dashboard', sa.Boolean(), nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nome'),
    )

    # ── Assinaturas ───────────────────────────────────────────────────────────
    op.create_table(
        'subscription',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('stripe_subscription_id', sa.String(length=100), nullable=True),
        sa.Column('periodo_inicio', sa.DateTime(), nullable=False),
        sa.Column('periodo_fim', sa.DateTime(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.Column('atualizado_em', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['plan_id'], ['plan.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── API Keys ──────────────────────────────────────────────────────────────
    op.create_table(
        'api_key',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column('key_hash', sa.String(length=256), nullable=False),
        sa.Column('key_prefix', sa.String(length=12), nullable=False),
        sa.Column('ultima_uso', sa.DateTime(), nullable=True),
        sa.Column('total_requisicoes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash'),
    )

    # ── Tokens de reset de senha ──────────────────────────────────────────────
    op.create_table(
        'password_reset_token',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=256), nullable=False),
        sa.Column('expira_em', sa.DateTime(), nullable=False),
        sa.Column('usado', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )


def downgrade():
    op.drop_table('password_reset_token')
    op.drop_table('api_key')
    op.drop_table('subscription')
    op.drop_table('plan')

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('stripe_customer_id')
        batch_op.drop_column('email_verificado')
        batch_op.drop_column('role')
