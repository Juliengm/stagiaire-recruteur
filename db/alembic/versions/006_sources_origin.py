"""La base devient la source de vérité des sources : origine et champs modifiés dans l'interface."""
from alembic import op

revision = "006"
down_revision = "005"


def upgrade() -> None:
    # 001 crée les tables depuis les modèles courants : les colonnes peuvent déjà exister
    op.execute("ALTER TABLE sources ADD COLUMN IF NOT EXISTS origin TEXT NOT NULL DEFAULT 'yaml'")
    op.execute("ALTER TABLE sources ADD COLUMN IF NOT EXISTS user_fields TEXT[] NOT NULL DEFAULT '{}'")


def downgrade() -> None:
    op.execute("ALTER TABLE sources DROP COLUMN IF EXISTS user_fields")
    op.execute("ALTER TABLE sources DROP COLUMN IF EXISTS origin")
