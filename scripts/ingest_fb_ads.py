"""
scripts/ingest_fb_ads.py
------------------------
Facebook Marketing API ingestion & optimization script.

In addition to ingesting campaigns and leads, this module evaluates
underperforming campaigns against revenue metrics. If a campaign is
wasting spend, it triggers an AI (Claude Sonnet) split-test generation
routine to recommend better copy or targeting.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd
import litellm

from config import settings
from core.db import AdCampaign, Lead, get_session
from core.slack import slack

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
SPLIT_TEST_PROMPT = """
You are an expert Performance Marketer for a remodeling contractor.
The following Facebook ad campaign has a low CTR and high spend.
Campaign Name: {campaign_name}
Objective: {objective}
Provide 3 completely different ad hook/copy angles we can test to improve CTR.
Return ONLY a plain text bulleted list of 3 angles (no intro/outro).
""".strip()


# ---------------------------------------------------------------------------
# Mock data — mirrors Facebook Marketing API response shape
# ---------------------------------------------------------------------------

MOCK_FB_CAMPAIGNS: list[dict[str, Any]] = [
    {
        "id": "120201111111111",
        "name": "Kitchen Remodel — Lead Gen Q1 2026",
        "status": "ACTIVE",
        "objective": "LEAD_GENERATION",
        "spend": "1450.75",
        "impressions": "82000",
        "clicks": "1340",    # ~1.6% CTR (good)
        "date_start": "2026-01-10",
        "date_stop": "2026-03-16",
    },
    {
        "id": "120202222222222",
        "name": "Bathroom Renovation — Retargeting Mar 2026",
        "status": "ACTIVE",
        "objective": "CONVERSIONS",
        "spend": "620.00",
        "impressions": "30500",
        "clicks": "520",     # ~1.7% CTR (good)
        "date_start": "2026-03-01",
        "date_stop": "2026-03-16",
    },
    {
        "id": "120203333333333",
        "name": "Full Home Remodel — Brand Awareness Q1 2026",
        "status": "ACTIVE",
        "objective": "REACH",
        "spend": "3200.50",
        "impressions": "510000",
        "clicks": "1900",     # ~0.37% CTR (very poor!)
        "date_start": "2026-01-15",
        "date_stop": "2026-03-16",
    },
]

MOCK_FB_LEADS = [
    {
        "full_name": "Maria González",
        "phone": "+1-305-555-0101",
        "email": "maria.g@example.com",
        "source_ad_id": "120201111111111",
    },
]

# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def generate_split_test_ideas(campaign_name: str, objective: str) -> list[str]:
    """Call Claude Sonnet to generate A/B test variations for low CTR campaigns."""
    if settings.MOCK_MODE:
        return [
            "Angle 1 (Pain Point): 'Tired of your outdated 1990s floor plan?'",
            "Angle 2 (Aspirational): 'Unlock the true value of your home with our luxury finishes.'",
            "Angle 3 (Trust): 'Voted #1 Contractor in 2025 by locals. Book an estimate today.'",
        ]

    prompt = SPLIT_TEST_PROMPT.format(campaign_name=campaign_name, objective=objective)
    response = litellm.completion(
        model=settings.LLM_FAST_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=200,
    )
    ideas_text = response.choices[0].message.content.strip()
    # parse the bullet points
    return [line.lstrip("-*• ") for line in ideas_text.split("\n") if line.strip()]


def evaluate_campaigns_for_optimization(df: pd.DataFrame) -> None:
    """Analyze campaign performance and trigger Slack alerts with AI ideas if poor."""
    # Simple logic: If CTR is below 0.5% and spend > $500, trigger optimization
    df["ctr"] = (df["clicks"] / df["impressions"]) * 100
    poor_performers = df[(df["ctr"] < 0.5) & (df["spend_usd"] > 500) & (df["status"] == "ACTIVE")]

    for _, row in poor_performers.iterrows():
        logger.info("  ⚠️ Poor campaign detected: %s (CTR: %.2f%%)", row["campaign_name"], row["ctr"])
        ideas = generate_split_test_ideas(row["campaign_name"], row["objective"])
        
        # Post to Slack
        slack.send_ad_recommendation(
            campaign_name=row["campaign_name"],
            ad_id=row["ad_id"],
            current_ctr=row["ctr"],
            split_test_ideas=ideas,
        )


def fetch_campaigns_from_api() -> list[dict[str, Any]]:
    if settings.MOCK_MODE: return MOCK_FB_CAMPAIGNS
    raise NotImplementedError("Set MOCK_MODE=false")

def fetch_leads_from_api() -> list[dict[str, Any]]:
    if settings.MOCK_MODE: return MOCK_FB_LEADS
    raise NotImplementedError("Set MOCK_MODE=false")

def normalize_campaigns(raw: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(raw)
    df["spend_usd"] = df["spend"].astype(float)
    df["impressions"] = df["impressions"].astype(int)
    df["clicks"] = df["clicks"].astype(int)
    df["date_start"] = pd.to_datetime(df["date_start"], errors="coerce")
    df["date_stop"] = pd.to_datetime(df["date_stop"], errors="coerce")
    df = df.rename(columns={"id": "ad_id", "name": "campaign_name"})
    return df

def upsert_campaigns(df: pd.DataFrame, session) -> int:
    inserted = 0
    existing_ids = {r[0] for r in session.query(AdCampaign.ad_id).all()}
    for _, row in df.iterrows():
        if row["ad_id"] in existing_ids: continue
        campaign = AdCampaign(
            ad_id=row["ad_id"], campaign_name=row["campaign_name"],
            status=row["status"], objective=row["objective"],
            spend_usd=row["spend_usd"], impressions=row["impressions"], clicks=row["clicks"],
        )
        session.add(campaign)
        inserted += 1
    session.commit()
    return inserted

def upsert_leads(raw_leads: list[dict[str, Any]], session) -> int:
    inserted = 0
    for lead_data in raw_leads:
        lead = Lead(
            full_name=lead_data["full_name"], phone=lead_data.get("phone"),
            email=lead_data.get("email"), source="facebook_lead_ad",
            source_ad_id=lead_data.get("source_ad_id"), status="NEW",
        )
        session.add(lead)
        inserted += 1
    session.commit()
    return inserted


def run_ingestion(engine=None) -> dict[str, int]:
    logger.info("=" * 60)
    logger.info("Starting Facebook Ads pipeline (Ingestion + AI Optimization)")
    logger.info("=" * 60)
    session = get_session(engine)
    try:
        raw_campaigns = fetch_campaigns_from_api()
        df_campaigns = normalize_campaigns(raw_campaigns)
        n_camp = upsert_campaigns(df_campaigns, session)
        
        # Run the AI Optimization module
        evaluate_campaigns_for_optimization(df_campaigns)

        raw_leads = fetch_leads_from_api()
        n_leads = upsert_leads(raw_leads, session)
        return {"campaigns_inserted": n_camp, "leads_inserted": n_leads}
    except Exception as exc:
        session.rollback()
        raise
    finally:
        session.close()
