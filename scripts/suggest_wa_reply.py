"""
scripts/suggest_wa_reply.py
---------------------------
WhatsApp AI Reply Suggestion Pipeline.

PRODUCTION BEHAVIOUR:
    When a WhatsApp message is flagged as URGENT by the initial triage,
    this script reads the context, calls Claude Sonnet to draft a professional,
    de-escalating reply, and pushes that suggestion to the project manager
    via a Slack button. They can click "Approve" to send it instantly via the
    WhatsApp API.

MOCK BEHAVIOUR:
    Simulates checking the DB for un-replied URGENT messages, generating
    a mocked Sonnet response, and logging the Slack notification.

LLM STRATEGY:
    Uses `claude-sonnet-4-5` for fast, cost-effective conversational drafting.
"""

from __future__ import annotations

import logging
from typing import Any

import litellm

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

REPLY_SYSTEM_PROMPT = """
You are an empathetic, highly professional Project Manager for a construction company.
A client has sent an URGENT or angry WhatsApp message.
Your job is to draft a reply that:
1. Validates their concern immediately.
2. Assures them the team is taking immediate action.
3. Keeps the tone calm and professional.
4. Is concise (under 3 sentences).

Format response as plain text. Do not include placeholders, just the exact message.
""".strip()


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def generate_reply_suggestion(message_body: str) -> str:
    """Generate a reply using Claude Sonnet."""
    if settings.MOCK_MODE:
        if "water pipe burst" in message_body.lower():
            return "I am so sorry about this emergency. I have just dispatched our emergency plumber to your property right now, and I will be there personally in 20 minutes to assess."
        return "We have received your urgent message and are looking into it immediately. We will call you within 10 minutes with an update."

    # --- Production Path ---
    response = litellm.completion(
        model=settings.LLM_FAST_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        messages=[
            {"role": "system", "content": REPLY_SYSTEM_PROMPT},
            {"role": "user", "content": f"Client Urgent Message:\n{message_body}"},
        ],
        temperature=0.3,
        max_tokens=150,
    )
    return response.choices[0].message.content.strip()

# NOTE: This function can be called seamlessly from `process_whatsapp.py`
# when an URGENT message is detected. See main.py logic integration.
