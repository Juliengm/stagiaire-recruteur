"""Compteur d'exécutions sans offre nouvelle par source (check « source muette »)."""
from alembic import op

revision = "002"
down_revision = "001"


def upgrade() -> None:
    # 001 crée les tables depuis les modèles courants : la colonne peut déjà exister
    op.execute("ALTER TABLE sources ADD COLUMN IF NOT EXISTS consecutive_empty_runs "
               "INTEGER NOT NULL DEFAULT 0")


def downgrade() -> None:
    op.execute("ALTER TABLE sources DROP COLUMN IF EXISTS consecutive_empty_runs")
