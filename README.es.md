# Motor de Atribución de Ingresos y Analítica de Leads con IA

[![CI](https://github.com/SerjCallier/ai-system-builder-showcase/actions/workflows/ci.yml/badge.svg)](https://github.com/SerjCallier/ai-system-builder-showcase/actions)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-336791?logo=postgresql&logoColor=white)
![LiteLLM](https://img.shields.io/badge/LiteLLM-Multi--Provider-6366f1)
![Licencia](https://img.shields.io/badge/license-MIT-green.svg)

[English](README.md) | **Español**

Prueba de concepto arquitectónica sanitizada para un **motor centralizado de orquestación IA y atribución de ingresos** que unifica inversión publicitaria, triage de mensajería, pipelines SEO y contratos cerrados en un esquema relacional PostgreSQL mediante SQLAlchemy y LiteLLM.

---

## Resumen Ejecutivo

En lugar de medir métricas de vanidad (formularios sin contexto), el sistema cierra el ciclo de atribución entre adquisición, mensajería operativa e ingresos reales:

1. **Atribución Real de Ingresos (ROAS):** Joins relacionales (`ad_campaigns -> leads -> projects`) calculan el retorno real contra contratos cerrados.
2. **Triage de Urgencias y Respuestas:** Clasifica mensajes operativos entrantes de WhatsApp y envía alertas estructuradas con Slack Block Kit.
3. **Enrutamiento Multi-Modelo por Niveles:** Utiliza `litellm` para enrutar clasificación de baja latencia, redacción SEO JSON-LD y fallback local offline bajo una interfaz unificada.

---

## Verificación y Ejecución Local

```bash
git clone https://github.com/SerjCallier/ai-system-builder-showcase.git
cd ai-system-builder-showcase

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Ejecutar tests offline de esquema SQLAlchemy y atribución ROAS (SQLite en memoria)
python -m unittest discover -s tests -v

# Verificar sintaxis de todos los módulos
python -m compileall -q config.py main.py core scripts tests
```

---

## Licencia

MIT © [Sergio Callier](https://github.com/SerjCallier)
