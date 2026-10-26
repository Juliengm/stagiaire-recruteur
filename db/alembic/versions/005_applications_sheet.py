"""Origine des candidatures importées du fichier Excel (onglet, N°) : réimport sans doublon."""
from alembic import op

revision = "005"
down_revision = "004"


def upgrade() -> None:
    # 001 crée les tables depuis les modèles courants : colonnes et contrainte peuvent exister
    op.execute("ALTER TABLE applications ADD COLUMN IF NOT EXISTS sheet TEXT")
    op.execute("ALTER TABLE applications ADD COLUMN IF NOT EXISTS sheet_row INTEGER")
    op.execute("""DO $$ BEGIN
        ALTER TABLE applications ADD CONSTRAINT applications_sheet_sheet_row_key
            UNIQUE (sheet, sheet_row);
    EXCEPTION WHEN duplicate_table OR duplicate_object THEN NULL; END $$""")


def downgrade() -> None:
    op.execute("ALTER TABLE applications DROP CONSTRAINT IF EXISTS applications_sheet_sheet_row_key")
    op.execute("ALTER TABLE applications DROP COLUMN IF EXISTS sheet_row")
    op.execute("ALTER TABLE applications DROP COLUMN IF EXISTS sheet")
