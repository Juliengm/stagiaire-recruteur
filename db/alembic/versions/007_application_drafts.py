"""Brouillons de candidature : préparés par /candidatures, relus dans l'interface, déposés dans Gmail."""
from alembic import op

revision = "007"
down_revision = "006"


def upgrade() -> None:
    # 001 crée les tables depuis les modèles courants : rejouable (IF NOT EXISTS)
    op.execute("""CREATE TABLE IF NOT EXISTS application_drafts (
        id BIGSERIAL PRIMARY KEY, offer_id BIGINT REFERENCES offers(id),
        organization TEXT, position TEXT NOT NULL, language TEXT, segment TEXT,
        cv_file TEXT, recipient TEXT, cc TEXT[] NOT NULL DEFAULT '{}', subject TEXT NOT NULL,
        email_html TEXT NOT NULL, letter_html TEXT NOT NULL, letter_filename TEXT NOT NULL,
        required_documents TEXT, weaknesses TEXT, apply_url TEXT,
        status TEXT NOT NULL DEFAULT 'draft', gmail_draft_id TEXT, gmail_thread_id TEXT,
        deposited_at TIMESTAMPTZ, sent_at DATE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
    op.execute("ALTER TABLE applications ADD COLUMN IF NOT EXISTS draft_id BIGINT "
               "REFERENCES application_drafts(id)")


def downgrade() -> None:
    op.execute("ALTER TABLE applications DROP COLUMN IF EXISTS draft_id")
    op.execute("DROP TABLE IF EXISTS application_drafts")
