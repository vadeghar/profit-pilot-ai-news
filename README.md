# Profit Pilot AI News

AI-driven Indian market news intelligence and paper-trading platform.

## Current foundation

The repository now contains the first runnable architecture slice:

- Python 3.12 + FastAPI backend
- Pydantic/Pydantic Settings configuration and domain contracts
- Provider interfaces for news, market data, LLM analysis, and paper execution
- Stub LLM provider for deterministic development
- REST health and Market Brain snapshot endpoints
- WebSocket Market Brain event stream
- Angular 22 frontend foundation with a live Market Brain shell
- Docker Compose development infrastructure for PostgreSQL and Redis
- pytest, Ruff, and mypy project configuration

## Planned flow

`News Sources → Normalize/Deduplicate → Entity Resolution → AI Analysis → Deterministic Signal/Risk → Paper Trade → Outcome → Market Brain`

The system will support PRE-MARKET, MARKET HOURS, and POST-MARKET states and keep AI decisions auditable through versioned prompts, model metadata, structured decisions, signals, and trade outcomes.

## Safety boundary

This project is **paper-trading only** during the initial development phases. No live broker execution is implemented.

## Development

Backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --app-dir backend
```

Frontend:

```bash
cd frontend
npm install
npm start
```

Infrastructure:

```bash
docker compose up --build
```

The initial Market Brain connects to `ws://localhost:8000/ws/market-brain` and currently receives an empty snapshot until the ingestion pipeline is implemented.
