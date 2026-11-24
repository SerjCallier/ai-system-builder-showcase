# AI Revenue Attribution & Lead Analytics Engine

[![CI](https://github.com/SerjCallier/ai-system-builder-showcase/actions/workflows/ci.yml/badge.svg)](https://github.com/SerjCallier/ai-system-builder-showcase/actions)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-336791?logo=postgresql&logoColor=white)
![LiteLLM](https://img.shields.io/badge/LiteLLM-Multi--Provider-6366f1)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**English** | [Español](README.es.md)

Sanitized architectural proof of concept for a **centralized AI orchestration & revenue attribution engine** unifying ad spend, messaging triage, SEO content pipelines, and signed contract values inside a single relational PostgreSQL schema via SQLAlchemy and LiteLLM.

---

## Executive Summary

Instead of measuring vanity form leads, this system closes the attribution loop between marketing acquisition, customer messaging, and real closed revenue:

1. **Multi-Touch Revenue Attribution:** Relational joins (`ad_campaigns -> leads -> projects`) compute true ROAS against closed-won contracts.
2. **Urgency Triage & Reply Drafting:** Classifies incoming WhatsApp operational messages and dispatches structured Slack Block Kit alerts.
3. **Tiered Multi-Model Routing:** Uses `litellm` to route low-latency triage, deep SEO JSON-LD drafting, and local offline fallbacks behind a unified interface.

---

## System Architecture

```mermaid
graph TD
    classDef db fill:#e8f5e9,stroke:#4caf50,stroke-width:2px;
    classDef llm fill:#fff3e0,stroke:#ff9800,stroke-width:2px;
    classDef output fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px;

    subgraph Sources [External Data Sources]
        FB["Ad Campaigns API"]
        WA["WhatsApp Business"]
        SEM["SEMrush Keywords"]
        WP["WordPress CMS"]
    end

    subgraph Ingestion [Python Ingestion Layer]
        I_FB["ingest_fb_ads.py"]
        I_WA["process_whatsapp.py<br/>suggest_wa_reply.py"]
        I_SEO["ingest_semrush.py<br/>generate_seo_content.py"]
    end

    subgraph CoreBrain [Core Data & LLM Routing]
        subgraph DB [PostgreSQL / SQLAlchemy]
            T_ADS[("ad_campaigns")]
            T_LEADS[("leads")]
            T_PROJ[("projects")]
            T_WA[("whatsapp_messages")]
            T_SEO[("keywords & drafts")]
        end

        subgraph AI [Tiered LiteLLM Router]
            FAST["Fast Tier<br/>Urgency & Triage"]:::llm
            DEEP["Reasoning Tier<br/>SEO & JSON-LD"]:::llm
            LOCAL["Local Fallback<br/>Zero-Egress Ollama"]:::llm
        end
    end

    subgraph Output [Actionable Outputs]
        S_URG["Slack<br/>#alerts-urgent"]:::output
        S_APP["Slack<br/>#content-approval"]:::output
        ATTR["ROAS Attribution<br/>SQL Analytics"]:::db
    end

    FB --> I_FB --> DB
    WA --> I_WA --> DB
    SEM --> I_SEO --> DB
    WP -. Auto-Publishing .- I_SEO

    DB <--> AI
    I_WA --> S_URG
    I_SEO --> S_APP
    DB --> ATTR

    T_ADS -. "source_ad_id" .-> T_LEADS
    T_LEADS -. "lead_id" .-> T_PROJ
```

---

## Verification & Local Run

```bash
git clone https://github.com/SerjCallier/ai-system-builder-showcase.git
cd ai-system-builder-showcase

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run offline SQLAlchemy schema & ROAS attribution unit tests (SQLite in-memory)
python -m unittest discover -s tests -v

# Syntax-check all modules
python -m compileall -q config.py main.py core scripts tests
```

---

## Project Structure

```text
ai-system-builder-showcase/
├── .github/workflows/ci.yml      # GitHub Actions syntax + schema ROAS tests
├── config.py                     # Sanitized env configuration & mock defaults
├── main.py                       # End-to-end simulation entrypoint
├── core/
│   ├── db.py                     # SQLAlchemy ORM models (Campaigns, Leads, Projects)
│   └── slack.py                  # Slack Block Kit alert builders
├── scripts/
│   ├── ingest_fb_ads.py          # Ad spend ingestion & ROI evaluator
│   ├── process_whatsapp.py       # Urgency classifier
│   ├── suggest_wa_reply.py       # Drafted response generator
│   ├── ingest_semrush.py         # Keyword pipeline
│   └── generate_seo_content.py   # Structured JSON-LD content generator
└── tests/
    └── test_smoke.py             # Offline ROAS join & sanitized config tests
```

---

## License

MIT © [Sergio Callier](https://github.com/SerjCallier)
