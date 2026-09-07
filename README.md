# Profit Pilot AI News

AI-driven Indian market news intelligence and paper-trading platform.

## Current foundation

The repository contains the first end-to-end development architecture slice:

- Python 3.12 + FastAPI backend
- Pydantic/Pydantic Settings configuration and domain contracts
- Provider interfaces for news, market data, LLM analysis, and execution
- Stub providers for deterministic development
- Free RSS/Atom news ingestion for the trial phase
- Canonical NSE entity resolution with company aliases
- Stable RSS event fingerprints and cross-feed deduplication
- Deterministic source reliability scoring
- SQLite persistence for news, AI decisions, paper orders, and positions
- Deterministic trading rules and risk engine
- Paper execution with realized and unrealized P&L
- Automated event-processing orchestration from news event through paper execution
- REST APIs for news, AI analysis, automated processing, trade intents, paper orders, positions, and Market Brain
- WebSocket Market Brain event stream with persisted graph data
- Angular 22 frontend foundation with Market Brain pipeline lanes and node inspector
- Docker Compose development infrastructure with SQLite persistence and Redis
- pytest, Ruff, and mypy project configuration

## Entity resolution

`EntityResolutionService` maps company names and aliases in news titles to canonical NSE symbols before persistence. The initial catalog covers major liquid names including RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, SBIN, ITC, BHARTIARTL, LT, HINDUNILVR, KOTAKBANK, AXISBANK, MARUTI, TATAMOTORS, SUNPHARMA, WIPRO, HCLTECH, ADANIENT and ADANIPORTS.

The resolver uses word-boundary matching to avoid obvious partial-word false positives and merges resolved symbols with any symbols already supplied by a news provider. The catalog is deliberately small and deterministic for the trial; a larger NSE master/security-reference dataset can replace it without changing the ingestion contract.

## Source reliability

`SourceReliabilityService` provides a deterministic 0–1 source-quality score and A–D tier. Initial defaults include higher scores for primary/regulatory sources and established financial publishers, with a neutral score for unknown sources. Source reliability is kept separate from AI materiality: a reliable source does not automatically make a story trade-worthy.

Use `GET /api/v1/news/{event_id}/source-reliability` to inspect the current score/tier for a persisted event.

## Free-first news trial

The trial does **not require paid news APIs**. Set `NEWS_PROVIDER=rss` and configure public RSS/Atom feeds in `NEWS_RSS_FEEDS`.

The RSS adapter retrieves feed metadata only (title, link/guid, publication time and feed source). It does not scrape article bodies. Feed failures are isolated so one unavailable feed does not prevent the other configured feeds from being processed.

A stable SHA-256-derived event ID is generated from the source, feed identifier/link, and normalized title. The provider removes duplicate events returned by multiple configured feeds. Entity resolution then enriches each event with canonical NSE symbols.

This free provider is an interchangeable implementation of `NewsProvider`. Later, licensed financial feeds, official company feeds, or social APIs can be added without changing the AI, risk, or paper-trading layers.

### Example configuration

```text
NEWS_PROVIDER=rss
NEWS_RSS_FEEDS=https://example.com/feed.xml,https://example.org/rss
NEWS_SYMBOL_KEYWORDS_JSON={"RELIANCE":["Reliance Industries","Reliance"],"TCS":["Tata Consultancy Services","TCS"]}
```

Do not assume every publisher permits automated retrieval from every public endpoint. The trial should use public feeds/endpoints that are permitted by their terms and robots/access policies; licensed feeds can be substituted later.

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

`Free RSS/Public Sources → Normalize/Deduplicate → Entity Resolution → Source Reliability → AI Analysis → Deterministic Signal/Risk → Paper Trade → Outcome → Market Brain`

Later, paid/licensed news APIs and official social APIs can replace or supplement the free providers. Provider-level performance will be measured so we can determine whether a paid source actually improves latency, coverage, signal quality, or P&L before purchasing it.

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
