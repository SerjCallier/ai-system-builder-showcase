"""
core/db.py
----------
SQLAlchemy ORM setup for the AI Brain PostgreSQL database.

Defines the core schema tables:
  - AdCampaigns   : Facebook ad spend and performance data
  - Leads         : Captured leads, linked back to source ad campaign
  - Projects      : Closed construction projects, linked to originating lead
  - WhatsAppMessages : Incoming group chat messages + LLM urgency category
  - SEOKeywords   : Pending keyword opportunities from SEMrush
  - ContentDrafts : Claude Opus generated blog posts matching SEO keywords
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship

from config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base declarative class
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Attribution Models (Ads -> Leads -> Projects)
# ---------------------------------------------------------------------------

class AdCampaign(Base):
    __tablename__ = "ad_campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ad_id = Column(String(64), unique=True, nullable=False, index=True)
    campaign_name = Column(String(256), nullable=False)
    status = Column(String(32), default="ACTIVE")
    objective = Column(String(64))
    spend_usd = Column(Float, default=0.0)
    impressions = Column(BigInteger, default=0)
    clicks = Column(Integer, default=0)
    date_start = Column(DateTime, nullable=True)
    date_stop = Column(DateTime, nullable=True)
    ingested_at = Column(DateTime, default=datetime.utcnow)

    leads = relationship("Lead", back_populates="campaign")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(256), nullable=False)
    phone = Column(String(32), nullable=True)
    email = Column(String(256), nullable=True)
    source = Column(String(64), default="facebook_lead_ad")
    source_ad_id = Column(String(64), ForeignKey("ad_campaigns.ad_id"), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    status = Column(String(32), default="NEW")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    campaign = relationship("AdCampaign", back_populates="leads")
    project = relationship("Project", back_populates="lead", uselist=False)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_name = Column(String(256), nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True, index=True)
    status = Column(String(32), default="IN_PROGRESS")
    contract_value_usd = Column(Float, default=0.0)
    whatsapp_group_id = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="project")
    messages = relationship("WhatsAppMessage", back_populates="project")


# ---------------------------------------------------------------------------
# Operations & Comm Models
# ---------------------------------------------------------------------------

class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(128), unique=True, nullable=False)
    group_id = Column(String(128), nullable=True)
    sender_phone = Column(String(32), nullable=False)
    sender_name = Column(String(256), nullable=True)
    body = Column(Text, nullable=False)
    urgency_category = Column(String(16), nullable=True, comment="URGENT|ROUTINE|FAQ")
    llm_reasoning = Column(Text, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="messages")


# ---------------------------------------------------------------------------
# SEO & Content Models (New addition)
# ---------------------------------------------------------------------------

class SEOKeyword(Base):
    """
    Ingested daily from SEMrush API.
    A priority list for the Claude Opus content generation pipeline.
    """
    __tablename__ = "seo_keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(256), nullable=False, unique=True, index=True)
    search_volume = Column(Integer, default=0)
    keyword_difficulty = Column(Integer, default=0)
    cpc_usd = Column(Float, default=0.0)
    search_intent = Column(String(64), nullable=True)
    serp_features = Column(Text, nullable=True)
    trend = Column(String(32), nullable=True)
    priority_score = Column(Integer, default=0, comment="Internal ranking score")
    status = Column(String(32), default="PENDING", comment="PENDING|DRAFTED|PUBLISHED")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    drafts = relationship("ContentDraft", back_populates="keyword")


class ContentDraft(Base):
    """
    Long-form SEO blog drafts generated by Claude Opus, pending human
    approval in Slack before publishing to WordPress.
    """
    __tablename__ = "content_drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword_id = Column(Integer, ForeignKey("seo_keywords.id"), nullable=False, index=True)
    generated_title = Column(String(256), nullable=False)
    content_body = Column(Text, nullable=False)
    json_ld_schema = Column(Text, nullable=True, comment="FAQ JSON-LD structured data")
    wp_draft_url = Column(String(512), nullable=True)
    status = Column(String(32), default="AWAITING_REVIEW", comment="AWAITING_REVIEW|APPROVED|REJECTED")
    created_at = Column(DateTime, default=datetime.utcnow)

    keyword = relationship("SEOKeyword", back_populates="drafts")


# ---------------------------------------------------------------------------
# Engine & Session
# ---------------------------------------------------------------------------

def get_engine(url: str | None = None, echo: bool = False):
    if settings.MOCK_MODE:
        return create_engine("sqlite:///:memory:", echo=echo)
    return create_engine(url or settings.database_url(), echo=echo)

def init_db(engine=None) -> None:
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Database schema initialized (including SEO tables).")

def get_session(engine=None) -> Session:
    if engine is None:
        engine = get_engine()
    return Session(engine)
