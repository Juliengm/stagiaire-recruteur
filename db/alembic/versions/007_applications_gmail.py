"""Candidatures préparées par /candidatures : brouillon et fil Gmail, pour repérer l'envoi."""
from alembic import op

revision = "007"
down_revision = "006"


def upgrade() -> None:
    # 001 crée les tables depuis les modèles courants : les colonnes peuvent déjà exister
    op.execute("ALTER TABLE applications ADD COLUMN IF NOT EXISTS gmail_draft_id TEXT")
    op.execute("ALTER TABLE applications ADD COLUMN IF NOT EXISTS gmail_thread_id TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE applications DROP COLUMN IF EXISTS gmail_thread_id")
    op.execute("ALTER TABLE applications DROP COLUMN IF EXISTS gmail_draft_id")
