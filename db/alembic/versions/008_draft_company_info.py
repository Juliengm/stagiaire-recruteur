"""Dossier de candidature : informations sur l'entreprise."""
from alembic import op

revision = "008"
down_revision = "007"


def upgrade() -> None:
    # 001 crée les tables depuis les modèles courants : rejouable (IF NOT EXISTS)
    op.execute("ALTER TABLE application_drafts ADD COLUMN IF NOT EXISTS company_info TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE application_drafts DROP COLUMN IF EXISTS company_info")
