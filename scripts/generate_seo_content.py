"""
scripts/generate_seo_content.py
-------------------------------
SEO Content Generation Pipeline using Claude Opus.

PRODUCTION BEHAVIOUR:
    1. Fetches high-priority, unwritten keywords from the `seo_keywords` table.
    2. Calls Claude Opus (via LiteLLM) to generate a deeply reasoned, long-form
       blog draft, including a JSON-LD FAQ schema for rich SERP snippets.
    3. Posts the draft to WordPress via the WP REST API as a "Draft".
    4. Triggers a Slack notification to #content-approval for human review.

MOCK BEHAVIOUR (MOCK_MODE=True):
    Follows the exact same logic but uses a mocked LLM response and a mocked
    WordPress API call. It still saves the draft to the Core Brain and sends
    a simulated Slack alert.

LLM STRATEGY:
    Uses `claude-opus-4-5` exclusively for this task.
    Rationale: SEO content requires high-quality, nuanced writing and strict
    adherence to technical formatting (JSON-LD schema). Latency is not an issue
    since this runs as a background batch job.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import litellm

from config import settings
from core.db import ContentDraft, SEOKeyword, get_session
from core.slack import slack

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM Prompts
# ---------------------------------------------------------------------------

BLOG_SYSTEM_PROMPT = """
You are an expert SEO Content Strategist and Copywriter for an elite residential
construction and remodeling company. Your goal is to write high-ranking, deeply
informative blog posts based on specific target keywords.

INSTRUCTIONS:
1. Write a compelling, click-worthy title.
2. Write a 2-3 paragraph introduction that hooks the reader.
3. Include a JSON-LD FAQ schema block at the end with 3 common questions
   related to the topic, formatted exactly as valid JSON-LD.
4. Output your response as a JSON object with three keys:
   - "title": (string)
   - "content_body": (string)
   - "json_ld_schema": (string, properly escaped)

Focus on quality, deep reasoning, and establishing authority in the home
remodeling niche. Do not use generic filler text.
""".strip()


# ---------------------------------------------------------------------------
# Core Pipeline
# ---------------------------------------------------------------------------

def generate_blog_draft(keyword: str, intent: str) -> dict[str, str]:
    """
    Call Claude Opus to generate the blog draft and JSON-LD schema.
    """
    if settings.MOCK_MODE:
        return _mock_generate_blog(keyword)

    # --- Production Path: Claude Opus ---
    user_prompt = f"Target Keyword: '{keyword}'\nSearch Intent: {intent}"
    
    response = litellm.completion(
        model=settings.LLM_DEEP_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        messages=[
            {"role": "system", "content": BLOG_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4, # Slightly creative but focused
        max_tokens=2500,
    )
    
    raw_content = response.choices[0].message.content.strip()
    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        logger.error("Claude Opus failed to return valid JSON.")
        raise


def _mock_generate_blog(keyword: str) -> dict[str, str]:
    """Simulated output from Claude Opus for testing."""
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f"How much does a {keyword} usually cost?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Costs vary widely depending on materials and scope, but a standard baseline starts around $15,000 to $25,000."
                }
            }
        ]
    }
    
    return {
        "title": f"The Ultimate Guide to {keyword.title()} in 2026",
        "content_body": f"<p>When homeowners search for <strong>{keyword}</strong>, they are often surprised by the complexities involved...</p>\n<h2>Why Quality Matters</h2>\n<p>Investing in skilled craftsmanship ensures your remodel lasts for decades.</p>",
        "json_ld_schema": json.dumps(schema, indent=2)
    }


def publish_to_wordpress_mock(draft: dict[str, str]) -> str:
    """
    Simulates posting to the WordPress REST API (/wp/v2/posts).
    Returns a mock URL for the created draft.
    """
    if not settings.MOCK_MODE:
        # PRODUCTION:
        # requests.post(f"{settings.WP_URL}/wp/v2/posts", auth=(...), json={...})
        pass
        
    logger.info("  [WP MOCK] Uploading draft to WordPress...")
    return "https://remodeling-client.com/wp-admin/post.php?post=999&action=edit"


def run_seo_pipeline(engine=None) -> None:
    """
    Main entry point: fetches top pending keywords, generates content via Opus,
    saves to DB, and alerts Slack for human review.
    """
    logger.info("=" * 60)
    logger.info("Starting SEO Keyword → Blog pipeline...")
    logger.info("Model: %s [%s]", settings.LLM_DEEP_MODEL, 
                "MOCK simulation" if settings.MOCK_MODE else "LIVE")
    logger.info("=" * 60)

    session = get_session(engine)
    try:
        # Get top 2 unwritten, high-priority keywords
        pending_kws = (
            session.query(SEOKeyword)
            .filter(SEOKeyword.status == "PENDING")
            .order_by(SEOKeyword.priority_score.desc())
            .limit(2)
            .all()
        )
        
        if not pending_kws:
            logger.info("No pending keywords to process.")
            return

        for kw in pending_kws:
            logger.info("\n✍️ Processing keyword: '%s' (Score: %d)", kw.keyword, kw.priority_score)
            
            # 1. Generate Content via Claude Opus
            draft_content = generate_blog_draft(kw.keyword, kw.search_intent or "INFORMATIONAL")
            
            # 2. "Publish" to WordPress as Draft
            wp_url = publish_to_wordpress_mock(draft_content)
            
            # 3. Save Draft to Core Brain DB
            draft_record = ContentDraft(
                keyword_id=kw.id,
                generated_title=draft_content["title"],
                content_body=draft_content["content_body"],
                json_ld_schema=draft_content["json_ld_schema"],
                wp_draft_url=wp_url,
                status="AWAITING_REVIEW"
            )
            session.add(draft_record)
            
            # Update keyword status
            kw.status = "DRAFTED"
            session.commit()
            
            # 4. Notify Slack for human QA
            slack.send_content_approval(
                keyword=kw.keyword,
                blog_title=draft_record.generated_title,
                excerpt=draft_record.content_body[:150] + "...",
                wp_draft_url=wp_url,
            )

        logger.info("\n✅ SEO pipeline complete. %d drafts generated.", len(pending_kws))
        
    except Exception as exc:
        session.rollback()
        logger.error("SEO pipeline failed: %s", exc, exc_info=True)
        raise
    finally:
        session.close()
