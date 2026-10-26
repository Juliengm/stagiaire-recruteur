"""Table des candidatures et relances (SPEC §3.2)."""
from alembic import op

revision = "004"
down_revision = "003"


def upgrade() -> None:
    # 001 crée les tables depuis les modèles courants : rejouable (IF NOT EXISTS)
    op.execute("""CREATE TABLE IF NOT EXISTS applications (
        id BIGSERIAL PRIMARY KEY, offer_id BIGINT REFERENCES offers(id),
        organization TEXT, contact TEXT, position TEXT, cv_sent TEXT, status TEXT,
        sent_at DATE, follow_up_at DATE, notes TEXT)""")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS applications")
