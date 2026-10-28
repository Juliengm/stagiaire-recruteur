"""Schéma de la base `veille` (SPEC §3.2), partagé entre pipeline et API."""
from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


EMBEDDING_DIM = 768  # intfloat/multilingual-e5-base ; changer de modèle impose une migration


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    region: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    priority: Mapped[int | None] = mapped_column(SmallInteger)
    schedule: Mapped[str] = mapped_column(Text, default="daily")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_empty_runs: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    origin: Mapped[str] = mapped_column(Text, default="yaml", server_default="yaml")  # yaml | api
    # champs modifiés depuis l'interface : sources_registry ne les reprend plus du YAML
    user_fields: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")


class RawOffer(Base):
    __tablename__ = "raw_offers"
    __table_args__ = (UniqueConstraint("source_id", "external_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    external_id: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    canonical_url: Mapped[str | None] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    organization: Mapped[str | None] = mapped_column(Text)
    location_text: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    contract_type: Mapped[str] = mapped_column(Text, default="unknown")
    language: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[date | None] = mapped_column(Date)
    deadline: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    fingerprint: Mapped[str | None] = mapped_column(Text, index=True)
    duplicate_of: Mapped[int | None] = mapped_column(ForeignKey("offers.id"))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)


class OfferSource(Base):
    __tablename__ = "offer_sources"

    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), primary_key=True)
    raw_offer_id: Mapped[int] = mapped_column(ForeignKey("raw_offers.id"), primary_key=True)


class OfferScore(Base):
    __tablename__ = "offer_scores"

    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), primary_key=True)
    rule_score: Mapped[float | None]
    final_score: Mapped[float | None]
    recommended_cv: Mapped[str | None] = mapped_column(Text)
    matched_keywords: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    embed_score: Mapped[float | None]
    embed_cv: Mapped[str | None] = mapped_column(Text)  # CV le plus proche sémantiquement
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserStatus(Base):
    __tablename__ = "user_status"

    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), primary_key=True)
    status: Mapped[str] = mapped_column(Text, default="new")
    note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    channel: Mapped[str] = mapped_column(Text)
    offer_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), default=list)


class CvProfile(Base):
    __tablename__ = "cv_profiles"

    code: Mapped[str] = mapped_column(Text, primary_key=True)  # nom du fichier cv/<code>.md
    text_content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(EMBEDDING_DIM))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OfferEmbedding(Base):
    __tablename__ = "offer_embeddings"

    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), primary_key=True)
    text_hash: Mapped[str] = mapped_column(Text)  # texte embarqué : recalcul s'il change
    embedding = mapped_column(Vector(EMBEDDING_DIM))


class Application(Base):
    """Candidatures et relances (reprend le fichier Excel de prospection, SPEC §3.2)."""

    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("sheet", "sheet_row"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    offer_id: Mapped[int | None] = mapped_column(ForeignKey("offers.id"))  # null : candidature spontanée
    organization: Mapped[str | None] = mapped_column(Text)
    contact: Mapped[str | None] = mapped_column(Text)
    position: Mapped[str | None] = mapped_column(Text)
    cv_sent: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[date | None] = mapped_column(Date)
    follow_up_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    sheet: Mapped[str | None] = mapped_column(Text)  # onglet du fichier Excel importé (Madagascar, Lille)
    sheet_row: Mapped[int | None] = mapped_column(Integer)  # colonne N° : clé de réimport
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("application_drafts.id"))


class ApplicationDraft(Base):
    """Candidature préparée par /candidatures, relue dans l'interface, déposée en brouillon Gmail.

    Créée vide depuis l'interface (dossier à préparer) ou remplie par /candidatures.
    Statuts : draft (à relire) → deposited (dans Gmail) → sent (envoyée par Julien) | discarded.
    """

    __tablename__ = "application_drafts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    offer_id: Mapped[int | None] = mapped_column(ForeignKey("offers.id"))
    organization: Mapped[str | None] = mapped_column(Text)
    position: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    segment: Mapped[str | None] = mapped_column(Text)  # tech | institutionnel
    cv_file: Mapped[str | None] = mapped_column(Text)  # PDF de cv/pdf/
    recipient: Mapped[str | None] = mapped_column(Text)  # vide : candidature par portail
    cc: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    subject: Mapped[str] = mapped_column(Text)
    email_html: Mapped[str] = mapped_column(Text)
    letter_html: Mapped[str] = mapped_column(Text)
    letter_filename: Mapped[str] = mapped_column(Text)
    required_documents: Mapped[str | None] = mapped_column(Text)  # pièces à joindre soi-même
    weaknesses: Mapped[str | None] = mapped_column(Text)  # exigences non couvertes par les faits
    apply_url: Mapped[str | None] = mapped_column(Text)
    company_info: Mapped[str | None] = mapped_column(Text)  # l'organisation vue sous l'angle du poste
    status: Mapped[str] = mapped_column(Text, default="draft", server_default="draft")
    gmail_draft_id: Mapped[str | None] = mapped_column(Text)
    gmail_thread_id: Mapped[str | None] = mapped_column(Text)
    deposited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
