"""Capacidade: grupos, semanas e lancamentos (Fase 1 do porte Indicadores de Engenharia)."""

import sqlalchemy as sa
from alembic import op

revision = "0002_capacidade"
down_revision = "0001_template"
branch_labels = None
depends_on = None

TABLES = ("grupos", "semanas", "lancamentos")


def _tenant_columns():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def upgrade():
    op.create_table(
        "grupos",
        *_tenant_columns(),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("categoria", sa.String(5), nullable=False),
        sa.Column("icone", sa.String(16), nullable=False, server_default="📋"),
        sa.Column("cor", sa.String(7), nullable=False, server_default="#64748B"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("categoria IN ('BUILD','RUN')", name="ck_grupos_categoria"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_grupos_tenant_id"),
        sa.UniqueConstraint("tenant_id", "nome", name="uq_grupos_tenant_nome"),
    )
    op.create_index("ix_grupos_tenant_id", "grupos", ["tenant_id"])
    op.create_table(
        "semanas",
        *_tenant_columns(),
        sa.Column("identificacao", sa.String(60), nullable=False),
        sa.Column("data_inicio", sa.Date(), nullable=True),
        sa.Column("data_fim", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "data_inicio IS NULL OR data_fim IS NULL OR data_fim >= data_inicio", name="ck_semanas_periodo"
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_semanas_tenant_id"),
        sa.UniqueConstraint("tenant_id", "identificacao", name="uq_semanas_tenant_identificacao"),
    )
    op.create_index("ix_semanas_tenant_id", "semanas", ["tenant_id"])
    op.create_table(
        "lancamentos",
        *_tenant_columns(),
        sa.Column("grupo_id", sa.Uuid(), nullable=False),
        sa.Column("semana_id", sa.Uuid(), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(9), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("quantidade >= 0", name="ck_lancamentos_quantidade"),
        sa.CheckConstraint("status IN ('ABERTO','RESOLVIDO')", name="ck_lancamentos_status"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "grupo_id"],
            ["grupos.tenant_id", "grupos.id"],
            name="fk_lancamentos_grupo",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "semana_id"],
            ["semanas.tenant_id", "semanas.id"],
            name="fk_lancamentos_semana",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_lancamentos_tenant_id"),
    )
    op.create_index("ix_lancamentos_tenant_id", "lancamentos", ["tenant_id"])
    op.create_index("ix_lancamentos_tenant_semana", "lancamentos", ["tenant_id", "semana_id"])
    op.create_index("ix_lancamentos_tenant_grupo", "lancamentos", ["tenant_id", "grupo_id"])
    if op.get_bind().dialect.name == "postgresql":
        expression = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"
        for table in TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {table} USING ({expression}) WITH CHECK ({expression})")
            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO guilarde_app")


def downgrade():
    op.drop_table("lancamentos")
    op.drop_table("semanas")
    op.drop_table("grupos")
