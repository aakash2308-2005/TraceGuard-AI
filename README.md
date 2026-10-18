# TraceGuard AI

**Connect. Analyze. Uncover.**

Agentic AI-powered cybercrime investigation platform. Human-supervised specialized
agents correlate fragmented digital evidence (usernames, emails, domains, IPs, files,
public blockchain transactions) into provenance-aware findings, relationship graphs,
timelines, and transparent, uncertainty-aware reports — while a dedicated **Defense
Agent** actively hunts for contradictions and false leads.

Uploaded text, PDF, and Office (docx/xlsx/pptx) files are scanned for candidate
identifiers, which are auto-registered as case indicators for correlation.

> Decision-support tool. Not an autonomous law-enforcement decision-maker.

## Architecture

See [`docs/ARCHITECTURE_AND_DESIGN.md`](docs/ARCHITECTURE_AND_DESIGN.md) for the full,
approved design (requirements, agents, data model, APIs, IBM Z integration, security,
testing, and roadmap).

## Tech stack

- **Frontend:** React + TypeScript + Vite, Cytoscape.js graph, TanStack Query.
- **Backend:** Python + FastAPI + Pydantic, SQLAlchemy (async) + Alembic.
- **Orchestration:** LangGraph with typed state, checkpoints, and human review gates.
- **Data:** PostgreSQL, Neo4j, MinIO (S3-compatible object storage).
- **AI:** pluggable `LLMProvider` (OpenAI or offline mock).
- **IBM Z:** adapter boundary with a clearly-labelled simulated scoring mock (real
  ML-for-z/OS path available when access is configured).

## Quick start (Docker, demo)

```bash
cp .env.example .env            # adjust secrets as needed
docker compose -f infra/docker-compose.yml up --build
```

Then open:

- Dashboard: http://localhost:5173
- API docs:  http://localhost:8000/docs
- Health:    http://localhost:8000/health

Everything runs offline by default (`LLM_MODE=mock`, `*_MODE=mock`); no external API
keys are required for the demo.

## Repository layout

```
backend/    FastAPI app, agents, tools, persistence, integrations, migrations, tests
frontend/   React + TS dashboard
infra/      docker-compose, neo4j constraints, nginx
scripts/    seed data, evaluation, audit verification
data/        synthetic investigation scenarios
docs/        architecture, API, threat model, evaluation, setup, demo
```

## Documentation

- `docs/ARCHITECTURE_AND_DESIGN.md` — full approved design.
- `docs/SETUP.md` — install and run.
- `docs/DEMO_SCRIPT.md` — ~5 minute guided demo.
- `docs/API.md` — REST API reference (OpenAPI at `/docs`).
- `docs/IBMZ_INTEGRATION.md` — IBM Z boundary, simulated vs. real.
- `docs/THREAT_MODEL.md` — threats and mitigations.
- `docs/EVALUATION.md` — synthetic scenarios and metrics.
- `docs/TROUBLESHOOTING.md` — common issues.
- `docs/LIMITATIONS.md` — known limitations and deployment checklist.

## Demo seed

After the stack is up, load the showcase data:

```bash
docker compose -f infra/docker-compose.yml exec api python -m app.cli seed
```

Then sign in as `admin` / `ChangeMe123!` and follow `docs/DEMO_SCRIPT.md`.

## Status

Built in ten milestones (see the roadmap in the architecture doc). This is a demonstrable
hackathon build; it is **not** certified production-ready. Known limitations and a
pre-production checklist are tracked in `docs/LIMITATIONS.md`.
