"""
main.py
-------
Simulation entry point for the AI Systems Builder MVP.

Running this script executes the full mock data pipeline across all modules:
  1. Initialize the Core Brain database schema
  2. Ingest FB Ads -> evaluate ROI -> suggest AI A/B tests (Slack)
  3. Process WhatsApp messages -> classify urgency -> suggest AI replies (Slack)
  4. Ingest SEMrush Keywords -> Generate Claude Opus SEO Blogs (Slack)
  5. Print Attribution Report
"""

from __future__ import annotations

import logging
import sys

from config import settings
from core.db import AdCampaign, Lead, Project, WhatsAppMessage, get_engine, get_session, init_db
from scripts import ingest_fb_ads, process_whatsapp, ingest_semrush, generate_seo_content

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("main")


def seed_demo_project(engine) -> None:
    session = get_session(engine)
    try:
        if session.query(Project).count() > 0: return
        lead = session.query(Lead).filter(Lead.source_ad_id == "120201111111111").first()
        if not lead: return
        
        project = Project(
            project_name="González Kitchen Full Remodel",
            lead_id=lead.id,
            status="IN_PROGRESS",
            contract_value_usd=27_500.00,
            whatsapp_group_id="120363xxxxxx@g.us",
        )
        session.add(project)
        session.commit()
    finally:
        session.close()


def print_attribution_report(engine) -> None:
    session = get_session(engine)
    try:
        results = (
            session.query(
                AdCampaign.ad_id, AdCampaign.campaign_name,
                AdCampaign.spend_usd, Project.contract_value_usd
            )
            .join(Lead, Lead.source_ad_id == AdCampaign.ad_id)
            .join(Project, Project.lead_id == Lead.id)
            .all()
        )
        print("\n" + "=" * 70)
        print("📊  ATTRIBUTION REPORT — Ad Spend → Closed Revenue")
        print("=" * 70)
        for row in results:
            roas = row.contract_value_usd / row.spend_usd if row.spend_usd else 0
            print(f"  Campaign : {row.campaign_name}")
            print(f"  ROAS     : {roas:.1f}x (${row.spend_usd:,.0f} spend -> ${row.contract_value_usd:,.0f} rev)")
        print("=" * 70 + "\n")
    finally:
        session.close()


def main() -> None:
    logger.info("🚀 AI Systems Builder — MVP Simulation Starting")
    
    # 1. Boot
    engine = get_engine()
    init_db(engine)

    # 2. Ads Optimization Module
    ingest_fb_ads.run_ingestion(engine)
    seed_demo_project(engine)

    # 3. WhatsApp Monitoring & Triage Module
    process_whatsapp.run_processing(engine)

    # 4. SEO Keyword-to-Blog Pipeline Module
    ingest_semrush.run_ingestion(engine)
    generate_seo_content.run_seo_pipeline(engine)

    # 5. Output
    print_attribution_report(engine)
    logger.info("✅ Full end-to-end simulation complete.")

if __name__ == "__main__":
    main()
