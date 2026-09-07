import json

from app.domain.models import AiDecision, NewsEvent, PaperOrder, Position
from app.storage.database import SqliteDatabase


class NewsEventRepository:
    def __init__(self, database: SqliteDatabase) -> None:
        self.database = database

    def save(self, event: NewsEvent) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO news_events
                   (id, title, source, published_at, symbols_json, materiality)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     title=excluded.title,
                     source=excluded.source,
                     published_at=excluded.published_at,
                     symbols_json=excluded.symbols_json,
                     materiality=excluded.materiality""",
                (event.id, event.title, event.source, event.published_at,
                 json.dumps(event.symbols), event.materiality),
            )

    def get(self, event_id: str) -> NewsEvent | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM news_events WHERE id = ?", (event_id,)
            ).fetchone()
        if row is None:
            return None
        return NewsEvent(
            id=row["id"], title=row["title"], source=row["source"],
            published_at=row["published_at"], symbols=json.loads(row["symbols_json"]),
            materiality=row["materiality"],
        )

    def list_recent(self, limit: int = 50) -> list[NewsEvent]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM news_events ORDER BY published_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            NewsEvent(
                id=row["id"], title=row["title"], source=row["source"],
                published_at=row["published_at"], symbols=json.loads(row["symbols_json"]),
                materiality=row["materiality"],
            )
            for row in rows
        ]


class AiDecisionRepository:
    def __init__(self, database: SqliteDatabase) -> None:
        self.database = database

    def save(self, event_id: str, decision: AiDecision, prompt: str, input_snapshot: str) -> int:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """INSERT INTO ai_decisions
                   (news_event_id, signal, confidence, reasoning, prompt_version, model,
                    prompt_text, input_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_id, decision.signal.value, decision.confidence, decision.reasoning,
                 decision.prompt_version, decision.model, prompt, input_snapshot),
            )
            return int(cursor.lastrowid)

    def list_for_event(self, event_id: str) -> list[AiDecision]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """SELECT signal, confidence, reasoning, prompt_version, model
                   FROM ai_decisions WHERE news_event_id = ? ORDER BY id DESC""",
                (event_id,),
            ).fetchall()
        return [
            AiDecision(
                signal=row["signal"], confidence=row["confidence"], reasoning=row["reasoning"],
                prompt_version=row["prompt_version"], model=row["model"],
            )
            for row in rows
        ]


class PaperTradingRepository:
    def __init__(self, database: SqliteDatabase) -> None:
        self.database = database

    def save_order(self, order: PaperOrder) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO paper_orders
                   (id, event_id, symbol, side, quantity, fill_price, notional, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (order.id, order.event_id, order.symbol, order.side.value, order.quantity,
                 order.fill_price, order.notional, order.status, order.created_at),
            )

    def list_orders(self, limit: int = 50) -> list[PaperOrder]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM paper_orders ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            PaperOrder(
                id=row["id"], event_id=row["event_id"], symbol=row["symbol"],
                side=row["side"], quantity=row["quantity"], fill_price=row["fill_price"],
                notional=row["notional"], status=row["status"], created_at=row["created_at"],
            )
            for row in rows
        ]

    def get_position(self, symbol: str) -> Position | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM positions WHERE symbol = ?", (symbol,)
            ).fetchone()
        if row is None:
            return None
        return Position(
            symbol=row["symbol"], quantity=row["quantity"],
            average_price=row["average_price"], realized_pnl=row["realized_pnl"],
        )

    def save_position(self, position: Position) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO positions (symbol, quantity, average_price, realized_pnl)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(symbol) DO UPDATE SET
                     quantity=excluded.quantity,
                     average_price=excluded.average_price,
                     realized_pnl=excluded.realized_pnl""",
                (position.symbol, position.quantity, position.average_price, position.realized_pnl),
            )

    def list_positions(self) -> list[Position]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM positions ORDER BY symbol").fetchall()
        return [
            Position(
                symbol=row["symbol"], quantity=row["quantity"],
                average_price=row["average_price"], realized_pnl=row["realized_pnl"],
            )
            for row in rows
        ]
