"""Rotinas: catálogo de rotinas recorrentes e execuções por semana (Fase 2)."""

import sqlalchemy as sa
from alembic import op

revision = "0003_rotinas"
down_revision = "0002_capacidade"
branch_labels = None
depends_on = None

TABLES = ("rotinas", "rotina_execucoes")


def _tenant_columns():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def upgrade():
    op.create_table(
        "rotinas",
        *_tenant_columns(),
        sa.Column("titulo", sa.String(200), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("categoria", sa.String(5), nullable=False, server_default="RUN"),
        sa.Column("responsavel", sa.String(120), nullable=True),
        sa.Column("link_recurso", sa.String(500), nullable=True),
        sa.Column("tipo_agendamento", sa.String(24), nullable=False, server_default="SEMANAL"),
        sa.Column("dia_semana", sa.String(7), nullable=True),
        sa.Column("periodo", sa.String(8), nullable=False, server_default="Manhã"),
        sa.Column("dia_mes", sa.SmallInteger(), nullable=True),
        sa.Column("esforco_estimado_min", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("inicio_vigencia", sa.Date(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("categoria IN ('BUILD','RUN')", name="ck_rotinas_categoria"),
        sa.CheckConstraint(
            "tipo_agendamento IN ('SEMANAL','DIARIA','QUINZENAL','MENSAL_DIA_FIXO',"
            "'MENSAL_PRIMEIRO_UTIL','MENSAL_ULTIMO_UTIL')",
            name="ck_rotinas_tipo",
        ),
        sa.CheckConstraint(
            "dia_semana IS NULL OR dia_semana IN ('Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo')",
            name="ck_rotinas_dia_semana",
        ),
        sa.CheckConstraint("tipo_agendamento <> 'SEMANAL' OR dia_semana IS NOT NULL", name="ck_rotinas_semanal"),
        sa.CheckConstraint("periodo IN ('Manhã','Tarde','Integral')", name="ck_rotinas_periodo"),
        sa.CheckConstraint("dia_mes IS NULL OR dia_mes BETWEEN 1 AND 31", name="ck_rotinas_dia_mes"),
        sa.CheckConstraint(
            "tipo_agendamento <> 'MENSAL_DIA_FIXO' OR dia_mes IS NOT NULL", name="ck_rotinas_mensal_fixo"
        ),
        sa.CheckConstraint("esforco_estimado_min BETWEEN 0 AND 1440", name="ck_rotinas_esforco"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_rotinas_tenant_id"),
    )
    op.create_index("ix_rotinas_tenant_id", "rotinas", ["tenant_id"])
    op.create_index("ix_rotinas_tenant_ordem", "rotinas", ["tenant_id", "ordem"])
    op.create_table(
        "rotina_execucoes",
        *_tenant_columns(),
        sa.Column("rotina_id", sa.Uuid(), nullable=False),
        sa.Column("semana_id", sa.Uuid(), nullable=False),
        sa.Column("ocorrencia", sa.String(7), nullable=False),
        sa.Column("status", sa.String(9), nullable=False, server_default="PENDENTE"),
        sa.Column("concluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("concluido_por", sa.String(), nullable=True),
        sa.Column("esforco_real_min", sa.Integer(), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "ocorrencia IN ('SEMANA','Segunda','Terça','Quarta','Quinta','Sexta')",
            name="ck_rotina_execucoes_ocorrencia",
        ),
        sa.CheckConstraint("status IN ('PENDENTE','CONCLUIDA')", name="ck_rotina_execucoes_status"),
        sa.CheckConstraint(
            "esforco_real_min IS NULL OR esforco_real_min BETWEEN 0 AND 1440", name="ck_rotina_execucoes_esforco"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "rotina_id"],
            ["rotinas.tenant_id", "rotinas.id"],
            name="fk_rotina_execucoes_rotina",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "semana_id"],
            ["semanas.tenant_id", "semanas.id"],
            name="fk_rotina_execucoes_semana",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_rotina_execucoes_tenant_id"),
        sa.UniqueConstraint("tenant_id", "rotina_id", "semana_id", "ocorrencia", name="uq_rotina_execucoes_ocorrencia"),
    )
    op.create_index("ix_rotina_execucoes_tenant_id", "rotina_execucoes", ["tenant_id"])
    op.create_index("ix_rotina_execucoes_tenant_semana", "rotina_execucoes", ["tenant_id", "semana_id"])
    if op.get_bind().dialect.name == "postgresql":
        expression = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"
        for table in TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {table} USING ({expression}) WITH CHECK ({expression})")
            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO guilarde_app")


def downgrade():
    op.drop_table("rotina_execucoes")
    op.drop_table("rotinas")
