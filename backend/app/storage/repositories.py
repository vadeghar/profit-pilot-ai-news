import json

from app.domain.models import AiDecision, NewsEvent
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
