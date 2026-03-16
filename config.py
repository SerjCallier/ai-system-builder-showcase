"""
config.py
---------
Centralized configuration management using environment variables.
"""

import os
from dotenv import load_dotenv

# Load variables from .env file if it exists
load_dotenv()


class Settings:
    """Application-wide settings pulled from environment variables."""

    # -------------------------------------------------------------------------
    # Database (PostgreSQL — Core Brain)
    # -------------------------------------------------------------------------
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "ai_brain")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")

    @classmethod
    def database_url(cls) -> str:
        return (
            f"postgresql+psycopg2://{cls.DB_USER}:{cls.DB_PASSWORD}"
            f"@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
        )

    # -------------------------------------------------------------------------
    # LLM Configuration (via LiteLLM)
    # -------------------------------------------------------------------------
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "sk-ant-mock-key-000")
    
    # Fast & cost-efficient: real-time WhatsApp, A/B ad split ideas
    LLM_FAST_MODEL: str = os.getenv("LLM_FAST_MODEL", "claude-sonnet-4-5")
    # High-quality reasoning: SEO blog generation + JSON-LD
    LLM_DEEP_MODEL: str = os.getenv("LLM_DEEP_MODEL", "claude-opus-4-5")
    # Local fallback
    LLM_LOCAL_MODEL: str = os.getenv("LLM_LOCAL_MODEL", "ollama/llama3")

    # -------------------------------------------------------------------------
    # Slack Webhooks (Block Kit Interface)
    # -------------------------------------------------------------------------
    SLACK_WEBHOOK_URGENT: str = os.getenv("SLACK_WEBHOOK_URGENT", "https://hooks.slack.com/services/mock_urgent")
    SLACK_WEBHOOK_CONTENT: str = os.getenv("SLACK_WEBHOOK_CONTENT", "https://hooks.slack.com/services/mock_content")
    SLACK_WEBHOOK_ADS: str = os.getenv("SLACK_WEBHOOK_ADS", "https://hooks.slack.com/services/mock_ads")

    # -------------------------------------------------------------------------
    # External APIs
    # -------------------------------------------------------------------------
    FB_APP_ID: str = os.getenv("FB_APP_ID", "mock_fb_app_id")
    FB_APP_SECRET: str = os.getenv("FB_APP_SECRET", "mock_fb_app_secret")
    FB_ACCESS_TOKEN: str = os.getenv("FB_ACCESS_TOKEN", "mock_fb_access_token")
    FB_AD_ACCOUNT_ID: str = os.getenv("FB_AD_ACCOUNT_ID", "act_mock_123456789")

    WA_PHONE_NUMBER_ID: str = os.getenv("WA_PHONE_NUMBER_ID", "mock_wa_phone_id")
    WA_ACCESS_TOKEN: str = os.getenv("WA_ACCESS_TOKEN", "mock_wa_access_token")
    WA_VERIFY_TOKEN: str = os.getenv("WA_VERIFY_TOKEN", "mock_verify_token")

    SEMRUSH_API_KEY: str = os.getenv("SEMRUSH_API_KEY", "mock_semrush_api_key")

    MOCK_MODE: bool = os.getenv("MOCK_MODE", "true").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
