"""
scripts/ingest_semrush.py
--------------------------
SEMrush API keyword data ingestion script.

PRODUCTION BEHAVIOUR (with real credentials):
    Calls the SEMrush Keyword Overview API v3 and Keyword Database API
    to fetch daily keyword data for tracked terms relevant to the client's
    remodeling niche. Pulls:
      - search volume, keyword difficulty, CPC, and search intent
      - competitor rankings for the same keywords
      - SERP features (featured snippets, People Also Ask, etc.)
    Endpoint: GET https://api.semrush.com/
      ?type=phrase_these&key={API_KEY}&phrase={keyword}&database=us

MOCK BEHAVIOUR (current — MOCK_MODE=True):
    Returns a curated list of high-value remodeling keywords with realistic
    SEMrush-shaped metrics, then persists them to the `seo_keywords` table.
    These keywords feed directly into the generate_seo_content.py pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from config import settings
from core.db import SEOKeyword, get_session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mock data — mirrors SEMrush Keyword Overview API response shape
# ---------------------------------------------------------------------------

MOCK_SEMRUSH_KEYWORDS: list[dict[str, Any]] = [
    {
        "keyword": "kitchen remodel cost 2026",
        "search_volume": 18_100,
        "keyword_difficulty": 42,
        "cpc_usd": 4.85,
        "search_intent": "INFORMATIONAL",
        "serp_features": ["featured_snippet", "people_also_ask"],
        "trend": "rising",
    },
    {
        "keyword": "bathroom renovation near me",
        "search_volume": 27_000,
        "keyword_difficulty": 58,
        "cpc_usd": 7.20,
        "search_intent": "TRANSACTIONAL",
        "serp_features": ["local_pack", "reviews"],
        "trend": "stable",
    },
    {
        "keyword": "how long does a kitchen remodel take",
        "search_volume": 9_900,
        "keyword_difficulty": 35,
        "cpc_usd": 2.10,
        "search_intent": "INFORMATIONAL",
        "serp_features": ["people_also_ask", "featured_snippet"],
        "trend": "rising",
    },
    {
        "keyword": "kitchen remodel contractors [city]",
        "search_volume": 5_400,
        "keyword_difficulty": 61,
        "cpc_usd": 11.50,
        "search_intent": "TRANSACTIONAL",
        "serp_features": ["local_pack", "ads"],
        "trend": "stable",
    },
    {
        "keyword": "open concept kitchen remodel ideas",
        "search_volume": 14_800,
        "keyword_difficulty": 28,
        "cpc_usd": 1.90,
        "search_intent": "INFORMATIONAL",
        "serp_features": ["image_pack", "people_also_ask"],
        "trend": "rising",
    },
    {
        "keyword": "average cost of bathroom remodel",
        "search_volume": 33_100,
        "keyword_difficulty": 49,
        "cpc_usd": 5.60,
        "search_intent": "INFORMATIONAL",
        "serp_features": ["featured_snippet", "people_also_ask"],
        "trend": "stable",
    },
]


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def fetch_keywords_from_api(seed_terms: list[str] | None = None) -> list[dict[str, Any]]:
    """
    Retrieve keyword data from SEMrush API.

    PRODUCTION:
        import requests
        results = []
        for term in seed_terms:
            resp = requests.get(
                "https://api.semrush.com/",
                params={
                    "type": "phrase_these",
                    "key": settings.SEMRUSH_API_KEY,
                    "phrase": term,
                    "database": "us",
                    "export_columns": "Ph,Nq,Cp,Co,In",
                },
            )
            results.extend(parse_semrush_response(resp.text))
        return results

    MOCK:
        Returns a curated list of remodeling industry keywords.
    """
    if settings.MOCK_MODE:
        logger.info("[MOCK] Returning %d mock SEMrush keywords.", len(MOCK_SEMRUSH_KEYWORDS))
        return MOCK_SEMRUSH_KEYWORDS

    raise NotImplementedError("Set MOCK_MODE=false and configure SEMRUSH_API_KEY.")


def normalize_keywords(raw: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Normalize raw SEMrush API data into a clean DataFrame
    ready for database insertion.

    Calculates a composite `priority_score` that ranks keywords by
    opportunity = volume × (1 - difficulty/100), biased toward
    INFORMATIONAL intent (blog-friendly) and rising trends.
    """
    df = pd.DataFrame(raw)

    df["serp_features_str"] = df["serp_features"].apply(lambda x: ",".join(x) if x else "")

    # Priority score: high volume, low difficulty, informational intent
    df["priority_score"] = (
        df["search_volume"] * (1 - df["keyword_difficulty"] / 100)
        * df["trend"].map({"rising": 1.2, "stable": 1.0, "declining": 0.7})
        * df["search_intent"].map({"INFORMATIONAL": 1.3, "TRANSACTIONAL": 1.0, "NAVIGATIONAL": 0.6})
    ).round(0).astype(int)

    return df.sort_values("priority_score", ascending=False)


def upsert_keywords(df: pd.DataFrame, session) -> int:
    """
    Insert or update SEOKeyword rows.
    Existing keywords (matched by keyword text) are updated with fresh metrics.
    Returns the number of new records inserted.
    """
    inserted = 0
    existing = {r[0]: r[1] for r in session.query(SEOKeyword.keyword, SEOKeyword.id).all()}

    for _, row in df.iterrows():
        if row["keyword"] in existing:
            # Update metrics for existing keyword
            record = session.get(SEOKeyword, existing[row["keyword"]])
            record.search_volume = int(row["search_volume"])
            record.keyword_difficulty = int(row["keyword_difficulty"])
            record.cpc_usd = float(row["cpc_usd"])
            record.priority_score = int(row["priority_score"])
            record.updated_at = datetime.now(timezone.utc)
        else:
            record = SEOKeyword(
                keyword=row["keyword"],
                search_volume=int(row["search_volume"]),
                keyword_difficulty=int(row["keyword_difficulty"]),
                cpc_usd=float(row["cpc_usd"]),
                search_intent=row["search_intent"],
                serp_features=row["serp_features_str"],
                trend=row["trend"],
                priority_score=int(row["priority_score"]),
                status="PENDING",
            )
            session.add(record)
            inserted += 1

    session.commit()
    return inserted


def run_ingestion(engine=None) -> dict[str, int]:
    """
    Main entry point for the SEMrush ingestion pipeline.
    Fetches → normalizes → persists keyword data.

    Returns a summary dict with counts of inserted/updated records.
    """
    logger.info("=" * 60)
    logger.info("Starting SEMrush keyword ingestion pipeline...")
    logger.info("=" * 60)

    session = get_session(engine)
    try:
        raw = fetch_keywords_from_api()
        df = normalize_keywords(raw)

        logger.info("Top priority keyword: '%s' (score: %d)",
                    df.iloc[0]["keyword"], df.iloc[0]["priority_score"])

        n_inserted = upsert_keywords(df, session)
        total = len(df)

        logger.info("Keywords processed: %d total, %d new, %d updated.",
                    total, n_inserted, total - n_inserted)

        return {"keywords_processed": total, "new_inserted": n_inserted}

    except Exception as exc:
        session.rollback()
        logger.error("SEMrush ingestion failed: %s", exc, exc_info=True)
        raise
    finally:
        session.close()
