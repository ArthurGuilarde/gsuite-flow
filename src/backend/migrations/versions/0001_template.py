"""Infrastructure-only baseline for new applications; not an upgrade of 0001_suite."""

import sqlalchemy as sa
from alembic import op

revision = "0001_template"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "browser_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_browser_sessions_expires_at", "browser_sessions", ["expires_at"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON browser_sessions TO guilarde_app")
        op.execute("GRANT SELECT ON alembic_version TO guilarde_app")


def downgrade():
    op.drop_table("browser_sessions")
