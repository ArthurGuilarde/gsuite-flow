"""Despesas & Contratos: inventário, orçamento mensal e vínculo com iniciativas do FinOps (Fase 4)."""

import sqlalchemy as sa
from alembic import op

revision = "0005_despesas"
down_revision = "0004_finops"
branch_labels = None
depends_on = None

TABLES = ("despesas", "orcamentos_despesas")


def _tenant_columns():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def upgrade():
    op.create_table(
        "despesas",
        *_tenant_columns(),
        sa.Column("nome", sa.String(160), nullable=False),
        sa.Column("fornecedor", sa.String(120), nullable=True),
        sa.Column("categoria", sa.String(60), nullable=False),
        sa.Column("tipo_custo", sa.String(20), nullable=False),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("valor_anterior", sa.Numeric(14, 2), nullable=True),
        sa.Column("status_auditoria", sa.String(12), nullable=False, server_default="EM_REVISAO"),
        sa.Column("data_inicio", sa.Date(), nullable=True),
        sa.Column("data_renovacao", sa.Date(), nullable=True),
        sa.Column("responsavel", sa.String(120), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("mes_acao", sa.Date(), nullable=True),
        sa.Column("fonte_id", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("tipo_custo IN ('RECORRENTE_MENSAL','PONTUAL')", name="ck_despesas_tipo_custo"),
        sa.CheckConstraint(
            "status_auditoria IN ('EM_REVISAO','VALIDADO','DESPERDICIO','CANCELADO','RENEGOCIADO')",
            name="ck_despesas_status",
        ),
        sa.CheckConstraint("valor >= 0 AND (valor_anterior IS NULL OR valor_anterior >= 0)", name="ck_despesas_valor"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "fonte_id"],
            ["fontes_custo.tenant_id", "fontes_custo.id"],
            name="fk_despesas_fonte",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_despesas_tenant_id"),
    )
    op.create_index("ix_despesas_tenant_id", "despesas", ["tenant_id"])
    op.create_index("ix_despesas_tenant_status", "despesas", ["tenant_id", "status_auditoria"])
    op.create_index("ix_despesas_tenant_renovacao", "despesas", ["tenant_id", "data_renovacao"])
    op.create_table(
        "orcamentos_despesas",
        *_tenant_columns(),
        sa.Column("competencia", sa.Date(), nullable=False),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("valor >= 0", name="ck_orcamentos_despesas_valor"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_orcamentos_despesas_tenant_id"),
        sa.UniqueConstraint("tenant_id", "competencia", name="uq_orcamentos_despesas_competencia"),
    )
    op.create_index("ix_orcamentos_despesas_tenant_id", "orcamentos_despesas", ["tenant_id"])
    with op.batch_alter_table("iniciativas") as batch:
        batch.add_column(sa.Column("despesa_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("conversao_despesa", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_foreign_key(
            "fk_iniciativas_despesa",
            "despesas",
            ["tenant_id", "despesa_id"],
            ["tenant_id", "id"],
        )
        batch.create_index("ix_iniciativas_tenant_despesa", ["tenant_id", "despesa_id"])
    if op.get_bind().dialect.name == "postgresql":
        expression = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"
        for table in TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {table} USING ({expression}) WITH CHECK ({expression})")
            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO guilarde_app")


def downgrade():
    with op.batch_alter_table("iniciativas") as batch:
        batch.drop_index("ix_iniciativas_tenant_despesa")
        batch.drop_constraint("fk_iniciativas_despesa", type_="foreignkey")
        batch.drop_column("conversao_despesa")
        batch.drop_column("despesa_id")
    op.drop_table("orcamentos_despesas")
    op.drop_table("despesas")
