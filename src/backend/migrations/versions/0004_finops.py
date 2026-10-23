"""FinOps: perfis de custo/hora, fontes de custo, faturas e iniciativas com participantes (Fase 3)."""

import sqlalchemy as sa
from alembic import op

revision = "0004_finops"
down_revision = "0003_rotinas"
branch_labels = None
depends_on = None

TABLES = ("perfis_custo", "fontes_custo", "faturas", "iniciativas", "iniciativa_participantes")


def _tenant_columns():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def upgrade():
    op.create_table(
        "perfis_custo",
        *_tenant_columns(),
        sa.Column("nome", sa.String(80), nullable=False),
        sa.Column("custo_hora", sa.Numeric(12, 2), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("custo_hora >= 0", name="ck_perfis_custo_custo_hora"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_perfis_custo_tenant_id"),
        sa.UniqueConstraint("tenant_id", "nome", name="uq_perfis_custo_tenant_nome"),
    )
    op.create_index("ix_perfis_custo_tenant_id", "perfis_custo", ["tenant_id"])
    op.create_table(
        "fontes_custo",
        *_tenant_columns(),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("metrica_nome", sa.String(80), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_fontes_custo_tenant_id"),
        sa.UniqueConstraint("tenant_id", "nome", name="uq_fontes_custo_tenant_nome"),
    )
    op.create_index("ix_fontes_custo_tenant_id", "fontes_custo", ["tenant_id"])
    op.create_table(
        "faturas",
        *_tenant_columns(),
        sa.Column("fonte_id", sa.Uuid(), nullable=False),
        sa.Column("competencia", sa.Date(), nullable=False),
        sa.Column("valor_orcado", sa.Numeric(14, 2), nullable=True),
        sa.Column("valor_realizado", sa.Numeric(14, 2), nullable=False),
        sa.Column("metrica_valor", sa.Numeric(14, 2), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "valor_realizado >= 0 AND (valor_orcado IS NULL OR valor_orcado >= 0) "
            "AND (metrica_valor IS NULL OR metrica_valor >= 0)",
            name="ck_faturas_valores",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "fonte_id"],
            ["fontes_custo.tenant_id", "fontes_custo.id"],
            name="fk_faturas_fonte",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_faturas_tenant_id"),
        sa.UniqueConstraint("tenant_id", "fonte_id", "competencia", name="uq_faturas_fonte_competencia"),
    )
    op.create_index("ix_faturas_tenant_id", "faturas", ["tenant_id"])
    op.create_index("ix_faturas_tenant_competencia", "faturas", ["tenant_id", "competencia"])
    op.create_table(
        "iniciativas",
        *_tenant_columns(),
        sa.Column("titulo", sa.String(160), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("modo_calculo", sa.String(12), nullable=False),
        sa.Column("valor_mensal", sa.Numeric(14, 2), nullable=True),
        sa.Column("frequencia", sa.String(16), nullable=True),
        sa.Column("mes_inicio", sa.Date(), nullable=False),
        sa.Column("janela_meses", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("mes_encerramento", sa.Date(), nullable=True),
        sa.Column("fonte_id", sa.Uuid(), nullable=True),
        sa.Column("investimento_reais", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("investimento_horas", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("investimento_custo_hora", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("tipo IN ('MELHORIA','AUTOMACAO','OTIMIZACAO_CUSTO')", name="ck_iniciativas_tipo"),
        sa.CheckConstraint("modo_calculo IN ('DIRETO_REAIS','POR_TEMPO')", name="ck_iniciativas_modo"),
        sa.CheckConstraint("valor_mensal IS NULL OR valor_mensal >= 0", name="ck_iniciativas_valor_mensal"),
        sa.CheckConstraint(
            "frequencia IS NULL OR frequencia IN ('DIARIA_UTIL','DIARIA_CORRIDA','SEMANAL','QUINZENAL','MENSAL')",
            name="ck_iniciativas_frequencia",
        ),
        sa.CheckConstraint("janela_meses BETWEEN 1 AND 60", name="ck_iniciativas_janela"),
        sa.CheckConstraint(
            "mes_encerramento IS NULL OR mes_encerramento >= mes_inicio", name="ck_iniciativas_encerramento"
        ),
        sa.CheckConstraint(
            "investimento_reais >= 0 AND investimento_horas >= 0 AND investimento_custo_hora >= 0",
            name="ck_iniciativas_investimento",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "fonte_id"],
            ["fontes_custo.tenant_id", "fontes_custo.id"],
            name="fk_iniciativas_fonte",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_iniciativas_tenant_id"),
    )
    op.create_index("ix_iniciativas_tenant_id", "iniciativas", ["tenant_id"])
    op.create_index("ix_iniciativas_tenant_inicio", "iniciativas", ["tenant_id", "mes_inicio"])
    op.create_table(
        "iniciativa_participantes",
        *_tenant_columns(),
        sa.Column("iniciativa_id", sa.Uuid(), nullable=False),
        sa.Column("perfil_nome", sa.String(80), nullable=False),
        sa.Column("custo_hora", sa.Numeric(12, 2), nullable=False),
        sa.Column("qtd_pessoas", sa.Integer(), nullable=False),
        sa.Column("horas_antes", sa.Numeric(10, 2), nullable=False),
        sa.Column("horas_depois", sa.Numeric(10, 2), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "custo_hora >= 0 AND qtd_pessoas >= 1 AND horas_antes >= 0 AND horas_depois >= 0",
            name="ck_participantes_valores",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "iniciativa_id"],
            ["iniciativas.tenant_id", "iniciativas.id"],
            name="fk_participantes_iniciativa",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_iniciativa_participantes_tenant_id"),
    )
    op.create_index("ix_iniciativa_participantes_tenant_id", "iniciativa_participantes", ["tenant_id"])
    op.create_index("ix_participantes_tenant_iniciativa", "iniciativa_participantes", ["tenant_id", "iniciativa_id"])
    if op.get_bind().dialect.name == "postgresql":
        expression = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"
        for table in TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {table} USING ({expression}) WITH CHECK ({expression})")
            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO guilarde_app")


def downgrade():
    op.drop_table("iniciativa_participantes")
    op.drop_table("iniciativas")
    op.drop_table("faturas")
    op.drop_table("fontes_custo")
    op.drop_table("perfis_custo")
