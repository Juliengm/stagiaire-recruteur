"""Embeddings : profils de CV, vecteurs d'offres, score sémantique (phase 3)."""
from alembic import op
from db.models import EMBEDDING_DIM

revision = "003"
down_revision = "002"


def upgrade() -> None:
    # 001 crée les tables depuis les modèles courants : tout est donc rejouable (IF NOT EXISTS)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE offer_scores ADD COLUMN IF NOT EXISTS embed_score DOUBLE PRECISION")
    op.execute("ALTER TABLE offer_scores ADD COLUMN IF NOT EXISTS embed_cv TEXT")
    op.execute(f"""CREATE TABLE IF NOT EXISTS cv_profiles (
        code TEXT PRIMARY KEY, text_content TEXT NOT NULL, content_hash TEXT NOT NULL,
        embedding vector({EMBEDDING_DIM}), updated_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
    op.execute(f"""CREATE TABLE IF NOT EXISTS offer_embeddings (
        offer_id BIGINT PRIMARY KEY REFERENCES offers(id), text_hash TEXT NOT NULL,
        embedding vector({EMBEDDING_DIM}))""")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS offer_embeddings")
    op.execute("DROP TABLE IF EXISTS cv_profiles")
    op.execute("ALTER TABLE offer_scores DROP COLUMN IF EXISTS embed_cv")
    op.execute("ALTER TABLE offer_scores DROP COLUMN IF EXISTS embed_score")
