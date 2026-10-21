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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
