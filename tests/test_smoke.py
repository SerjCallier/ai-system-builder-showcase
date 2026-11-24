import importlib
import os
import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import config
from core.db import AdCampaign, Base, Lead, Project


class RevenueAttributionTests(unittest.TestCase):
    def test_settings_defaults_are_sanitized(self):
        with patch.dict(os.environ, {}, clear=True):
            reloaded = importlib.reload(config)
            self.assertIn("postgresql+psycopg2://", reloaded.settings.database_url())
            self.assertTrue(reloaded.settings.ANTHROPIC_API_KEY.startswith("sk-ant-mock"))
            self.assertTrue(reloaded.settings.MOCK_MODE)

    def test_attribution_schema_and_roas_join_in_memory(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            ad = AdCampaign(
                ad_id="ad-100",
                campaign_name="Search High Intent",
                spend_usd=500.0,
                impressions=12000,
                clicks=450,
            )
            session.add(ad)
            session.flush()

            lead = Lead(source_ad_id="ad-100", full_name="Sample Client")
            session.add(lead)
            session.flush()

            proj = Project(
                project_name="Commercial Buildout",
                lead_id=lead.id,
                status="CLOSED_WON",
                contract_value_usd=15000.0,
            )
            session.add(proj)
            session.commit()

            joined = (
                session.query(AdCampaign.spend_usd, Project.contract_value_usd)
                .join(Lead, Lead.source_ad_id == AdCampaign.ad_id)
                .join(Project, Project.lead_id == Lead.id)
                .one()
            )
            roas = joined.contract_value_usd / joined.spend_usd
            self.assertEqual(roas, 30.0)


if __name__ == "__main__":
    unittest.main()
