"""Demandas e Triagem: demandas pertencem aos grupos da Capacidade; Triagem é grupo de sistema (Fase 6)."""

import sqlalchemy as sa
from alembic import op

revision = "0007_demandas"
down_revision = "0006_planner"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("grupos") as batch:
        batch.add_column(sa.Column("sistema", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index(
        "uq_grupos_sistema",
        "grupos",
        ["tenant_id"],
        unique=True,
        sqlite_where=sa.text("sistema"),
        postgresql_where=sa.text("sistema"),
    )
    op.create_table(
        "demandas",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("grupo_id", sa.Uuid(), nullable=False),
        sa.Column("titulo", sa.String(200), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("prioridade", sa.String(5), nullable=False, server_default="MEDIA"),
        sa.Column("status", sa.String(10), nullable=False, server_default="ABERTA"),
        sa.Column("solicitante_sub", sa.String(255), nullable=False),
        sa.Column("classificado_por", sa.String(255), nullable=True),
        sa.Column("classificado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("concluido_por", sa.String(255), nullable=True),
        sa.Column("concluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("prioridade IN ('BAIXA','MEDIA','ALTA')", name="ck_demandas_prioridade"),
        sa.CheckConstraint("status IN ('ABERTA','CONCLUIDA','CANCELADA')", name="ck_demandas_status"),
        sa.CheckConstraint(
            "(concluido_em IS NOT NULL) = (status = 'CONCLUIDA')",
            name="ck_demandas_concluido",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "grupo_id"],
            ["grupos.tenant_id", "grupos.id"],
            name="fk_demandas_grupo",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_demandas_tenant_id"),
    )
    op.create_index("ix_demandas_tenant_id", "demandas", ["tenant_id"])
    op.create_index("ix_demandas_tenant_status", "demandas", ["tenant_id", "status"])
    op.create_index("ix_demandas_tenant_grupo", "demandas", ["tenant_id", "grupo_id"])
    op.create_index("ix_demandas_tenant_solicitante", "demandas", ["tenant_id", "solicitante_sub"])
    if op.get_bind().dialect.name == "postgresql":
        expression = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"
        op.execute("ALTER TABLE demandas ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE demandas FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON demandas USING ({expression}) WITH CHECK ({expression})")
        op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON demandas TO guilarde_app")


def downgrade():
    op.drop_table("demandas")
    op.drop_index("uq_grupos_sistema", table_name="grupos")
    with op.batch_alter_table("grupos") as batch:
        batch.drop_column("sistema")
