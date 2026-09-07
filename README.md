# Profit Pilot AI News

AI-driven Indian market news intelligence and paper-trading platform.

## Current foundation

The repository contains the first end-to-end development architecture slice:

- Python 3.12 + FastAPI backend
- Pydantic/Pydantic Settings configuration and domain contracts
- Provider interfaces for news, market data, LLM analysis, and execution
- Stub providers for deterministic development
- SQLite persistence for news, AI decisions, paper orders, and positions
- Deterministic trading rules and risk engine
- Paper execution with realized and unrealized P&L
- Automated event-processing orchestration from news event through paper execution
- REST APIs for news, AI analysis, automated processing, trade intents, paper orders, positions, and Market Brain
- WebSocket Market Brain event stream with persisted graph data
- Angular 22 frontend foundation with Market Brain pipeline lanes and node inspector
- Docker Compose development infrastructure with SQLite persistence and Redis
- pytest, Ruff, and mypy project configuration

## Automated event processing

A news event can now be processed through one API call:

`News Event → AI Analysis → Deterministic Trading Rules → Risk Engine → Paper Trade → Position/P&L`

Use `POST /api/v1/news/{event_id}/process` with optional `quantity` and `market_phase`. If an AI decision does not exist, the service creates one first. The same latest persisted decision is then passed through deterministic rules and risk checks. Only an approved intent reaches `PaperTradingService`.

Processing is idempotent at the news-event level: if a paper order already exists for the event, the service returns `ALREADY_EXECUTED` instead of creating another paper order.

The individual analyze, trade-intent, and execute endpoints remain available for debugging and controlled step-by-step workflows.

## Market Brain flow

`News Sources → AI Processing → Stocks → Signals → Paper Trades → Positions/P&L`

The Market Brain snapshot is built from persisted application state. Nodes expose metadata for source/time, AI reasoning/confidence, stock symbol, paper fill details, and position/P&L details. The WebSocket broadcasts a refreshed graph after ingestion, analysis, automated processing, trade-intent creation, and paper execution.

## Broker integration placeholder

Angel One SmartAPI is reserved as a replaceable provider boundary. The repository currently contains:

- `AngelOneMarketDataProvider` read-only market-data adapter
- `AngelOneBrokerProvider` disabled execution boundary
- `ANGEL_API_KEY`
- `ANGEL_CLIENT_CODE`
- `ANGEL_PASSWORD`
- `ANGEL_TOTP_SECRET`
- `ANGEL_SYMBOL_TOKENS_JSON`

These settings are placeholders only and remain empty in `.env.example`. **No Angel One order is made.** Paper trading remains the only execution path.

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

The Market Brain connects to `ws://localhost:8000/ws/market-brain`. It receives the current persisted graph immediately and receives refreshed snapshots when the backend changes the news/AI/paper-trading state.
