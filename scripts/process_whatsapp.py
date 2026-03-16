"""
scripts/process_whatsapp.py
---------------------------
WhatsApp Business API message processing pipeline.

PRODUCTION BEHAVIOUR (with real credentials):
    Receives webhook POST payloads from the Meta WhatsApp Cloud API.
    Calls Claude Sonnet to classify urgency. If URGENT, calls Sonnet again
    to generate a suggested reply, and posts both to the Slack #alerts-urgent
    channel via Block Kit.

MOCK BEHAVIOUR (current — MOCK_MODE=True):
    Simulates three incoming messages (URGENT / ROUTINE / FAQ), generating
    mocked Sonnet classifications and reply suggestions, logging the expected
    Slack payload.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import litellm

from config import settings
from core.db import WhatsAppMessage, get_session
from core.slack import slack
from scripts.suggest_wa_reply import generate_reply_suggestion

logger = logging.getLogger(__name__)

URGENCY_CATEGORIES = {"URGENT", "ROUTINE", "FAQ"}

CLASSIFICATION_SYSTEM_PROMPT = """
You are an AI assistant embedded in a construction project management system.
Classify this WhatsApp group chat message from an active remodeling project
into exactly one of these urgency categories:
- URGENT: Requires immediate attention (safety, damage, emergencies, angry clients).
- ROUTINE: Normal project communication (daily updates, logistics).
- FAQ: Simple, common questions (pricing, timelines).

Respond ONLY with valid JSON:
{"category": "URGENT", "reasoning": "One short sentence explaining why."}
""".strip()

# ---------------------------------------------------------------------------
# Mock incoming messages
# ---------------------------------------------------------------------------

MOCK_WHATSAPP_MESSAGES: list[dict[str, Any]] = [
    {
        "message_id": f"wamid.mock_{uuid.uuid4().hex[:12]}",
        "group_id": "120363xxxxxx@g.us",
        "sender_phone": "+13055550101",
        "sender_name": "Roberto (Site Foreman)",
        "body": "URGENT!! Water pipe burst in the kitchen wall we just opened up. Water is everywhere. Need a plumber HERE NOW. Client is freaking out.",
        "received_at": datetime.now(timezone.utc),
    },
    {
        "message_id": f"wamid.mock_{uuid.uuid4().hex[:12]}",
        "group_id": "120363yyy@g.us",
        "sender_phone": "+17865550199",
        "sender_name": "Ana (Project Coordinator)",
        "body": "Good morning team. Tile delivery confirmed for Thursday 9am.",
        "received_at": datetime.now(timezone.utc),
    },
]

# ---------------------------------------------------------------------------
# Core Logic
# ---------------------------------------------------------------------------

def classify_message_urgency(message_body: str) -> dict[str, str]:
    if settings.MOCK_MODE:
        if "burst" in message_body.lower() or "emergency" in message_body.lower():
            return {"category": "URGENT", "reasoning": "Message describes an active water leak causing property damage."}
        return {"category": "ROUTINE", "reasoning": "Operational logistics update."}
        
    response = litellm.completion(
        model=settings.LLM_FAST_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        messages=[
            {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": f"Message:\n{message_body}"},
        ],
        temperature=0.1,
        max_tokens=120,
    )
    raw_content = response.choices[0].message.content.strip()
    return json.loads(raw_content)

def save_message(msg_data: dict[str, Any], classification: dict[str, str], session) -> WhatsAppMessage:
    record = WhatsAppMessage(
        message_id=msg_data["message_id"],
        group_id=msg_data.get("group_id"),
        sender_phone=msg_data["sender_phone"],
        sender_name=msg_data.get("sender_name"),
        body=msg_data["body"],
        urgency_category=classification["category"],
        llm_reasoning=classification.get("reasoning"),
    )
    session.add(record)
    session.commit()
    return record


def run_processing(engine=None) -> list[dict[str, str]]:
    logger.info("=" * 60)
    logger.info("Starting WhatsApp processing & AI Reply Generation pipeline")
    logger.info("=" * 60)

    session = get_session(engine)
    results = []

    try:
        messages = MOCK_WHATSAPP_MESSAGES if settings.MOCK_MODE else []

        for i, msg in enumerate(messages, 1):
            logger.info("\n[%d/%d] Processing message from %s...", i, len(messages), msg["sender_name"])

            classification = classify_message_urgency(msg["body"])
            record = save_message(msg, classification, session)
            
            logger.info("  ✅ Classification → [%s] | Reasoning: %s",
                        classification["category"], classification["reasoning"])

            # Feature: Trigger Smart Reply Suggestions and Slack Block Kit Alert
            if record.urgency_category == "URGENT":
                # 1. Draft reply with Claude Sonnet
                logger.info("  ⚙️ Generating AI reply suggestion via Claude Sonnet...")
                suggested_text = generate_reply_suggestion(record.body)
                
                # 2. Push to Slack
                slack.send_urgent_alert(
                    sender_name=record.sender_name or "Unknown",
                    group_id=record.group_id or "Direct",
                    message_body=record.body,
                    reasoning=record.llm_reasoning or "",
                    suggested_reply=suggested_text,
                )

            results.append({
                "sender": msg["sender_name"],
                "category": classification["category"],
            })

        logger.info("\n✅ WA Processing complete. %d messages handled.", len(results))
        return results

    except Exception as exc:
        session.rollback()
        raise
    finally:
        session.close()
