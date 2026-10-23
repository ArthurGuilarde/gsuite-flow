"""Planner pessoal (Meu Dia): dias e itens privados por pessoa dentro do tenant (Fase 5)."""

import sqlalchemy as sa
from alembic import op

revision = "0006_planner"
down_revision = "0005_despesas"
branch_labels = None
depends_on = None

TABLES = ("planner_dias", "planner_itens")


def _tenant_columns():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def upgrade():
    op.create_table(
        "planner_dias",
        *_tenant_columns(),
        sa.Column("sub", sa.String(255), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("foco", sa.String(500), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_planner_dias_tenant_id"),
        sa.UniqueConstraint("tenant_id", "sub", "id", name="uq_planner_dias_tenant_sub_id"),
        sa.UniqueConstraint("tenant_id", "sub", "data", name="uq_planner_dias_sub_data"),
    )
    op.create_index("ix_planner_dias_tenant_id", "planner_dias", ["tenant_id"])
    op.create_index("ix_planner_dias_tenant_sub_data", "planner_dias", ["tenant_id", "sub", "data"])
    op.create_table(
        "planner_itens",
        *_tenant_columns(),
        sa.Column("sub", sa.String(255), nullable=False),
        sa.Column("dia_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("texto", sa.String(500), nullable=False),
        sa.Column("concluido", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("concluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("migrado_em", sa.Date(), nullable=True),
        sa.Column("descartado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("origem_item_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("tipo IN ('PRIORIDADE','TAREFA')", name="ck_planner_itens_tipo"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "sub", "dia_id"],
            ["planner_dias.tenant_id", "planner_dias.sub", "planner_dias.id"],
            name="fk_planner_itens_dia",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_planner_itens_tenant_id"),
    )
    op.create_index("ix_planner_itens_tenant_id", "planner_itens", ["tenant_id"])
    op.create_index("ix_planner_itens_tenant_sub_dia", "planner_itens", ["tenant_id", "sub", "dia_id"])
    if op.get_bind().dialect.name == "postgresql":
        # Pessoal dentro do tenant: a policy também restringe pelo sujeito (app.subject, definido em api/deps.py).
        expression = (
            "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid "
            "AND sub = current_setting('app.subject', true)"
        )
        for table in TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY planner_owner ON {table} USING ({expression}) WITH CHECK ({expression})")
            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO guilarde_app")


def downgrade():
    op.drop_table("planner_itens")
    op.drop_table("planner_dias")
