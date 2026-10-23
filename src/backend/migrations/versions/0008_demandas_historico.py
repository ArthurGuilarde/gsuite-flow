"""Demandas: histórico (linha do tempo) e comentários, com backfill dos eventos existentes."""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0008_demandas_historico"
down_revision = "0007_demandas"
branch_labels = None
depends_on = None


def upgrade():
    historico = op.create_table(
        "demanda_historico",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("demanda_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(12), nullable=False),
        sa.Column("autor_sub", sa.String(255), nullable=False),
        sa.Column("texto", sa.Text(), nullable=True),
        sa.Column("grupo_nome", sa.String(120), nullable=True),
        sa.CheckConstraint(
            "tipo IN ('ABERTURA','CLASSIFICACAO','CONCLUSAO','REABERTURA','CANCELAMENTO','COMENTARIO')",
            name="ck_demanda_historico_tipo",
        ),
        sa.CheckConstraint("(tipo <> 'COMENTARIO') OR (texto IS NOT NULL)", name="ck_demanda_historico_texto"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "demanda_id"],
            ["demandas.tenant_id", "demandas.id"],
            name="fk_demanda_historico_demanda",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_demanda_historico_tenant_id"),
    )
    op.create_index("ix_demanda_historico_tenant_id", "demanda_historico", ["tenant_id"])
    op.create_index(
        "ix_demanda_historico_tenant_demanda", "demanda_historico", ["tenant_id", "demanda_id", "created_at"]
    )
    postgresql = op.get_bind().dialect.name == "postgresql"
    if postgresql:
        # O owner também está sujeito ao FORCE RLS: libera a leitura só durante o backfill, na mesma transação.
        for tabela in ("demandas", "grupos"):
            op.execute(f"ALTER TABLE {tabela} NO FORCE ROW LEVEL SECURITY")
    _backfill(historico)
    if postgresql:
        for tabela in ("demandas", "grupos"):
            op.execute(f"ALTER TABLE {tabela} FORCE ROW LEVEL SECURITY")
        expression = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"
        op.execute("ALTER TABLE demanda_historico ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE demanda_historico FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON demanda_historico USING ({expression}) WITH CHECK ({expression})"
        )
        op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON demanda_historico TO guilarde_app")


def _backfill(historico):
    """Roda como owner (RLS liberada só neste passo, no PostgreSQL): percorre todas as demandas de todos os tenants."""
    conn = op.get_bind()
    dt = sa.DateTime(timezone=True)
    dem = sa.table(
        "demandas",
        sa.column("id", sa.Uuid()),
        sa.column("tenant_id", sa.Uuid()),
        sa.column("grupo_id", sa.Uuid()),
        sa.column("created_at", dt),
        sa.column("solicitante_sub", sa.String()),
        sa.column("classificado_por", sa.String()),
        sa.column("classificado_em", dt),
        sa.column("concluido_por", sa.String()),
        sa.column("concluido_em", dt),
        sa.column("cancelado_em", dt),
    )
    grp = sa.table(
        "grupos", sa.column("id", sa.Uuid()), sa.column("tenant_id", sa.Uuid()), sa.column("nome", sa.String())
    )
    demandas = conn.execute(sa.select(dem)).mappings()
    linhas = []

    def evento(d, tipo, autor, quando, grupo_nome=None):
        linhas.append(
            {
                "id": uuid4(),
                "tenant_id": d["tenant_id"],
                "created_by": autor,
                "created_at": quando,
                "demanda_id": d["id"],
                "tipo": tipo,
                "autor_sub": autor,
                "texto": None,
                "grupo_nome": grupo_nome,
            }
        )

    for d in list(demandas):
        evento(d, "ABERTURA", d["solicitante_sub"], d["created_at"])
        if d["classificado_em"] is not None:
            nome = conn.execute(
                sa.select(grp.c.nome).where(grp.c.tenant_id == d["tenant_id"], grp.c.id == d["grupo_id"])
            ).scalar()
            autor = d["classificado_por"] or d["solicitante_sub"]
            evento(d, "CLASSIFICACAO", autor, d["classificado_em"], nome)
        if d["concluido_em"] is not None:
            evento(d, "CONCLUSAO", d["concluido_por"] or d["solicitante_sub"], d["concluido_em"])
        if d["cancelado_em"] is not None:
            evento(d, "CANCELAMENTO", d["solicitante_sub"], d["cancelado_em"])
    if linhas:
        op.bulk_insert(historico, linhas)


def downgrade():
    op.drop_table("demanda_historico")
