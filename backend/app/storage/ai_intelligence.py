import json
from datetime import datetime, timezone
from typing import Any

from app.domain.models import AiDecision, NewsEvent
from app.storage.database import SqliteDatabase


class AiQueueRepository:
    """Persistent queue for news waiting for AI analysis."""

    def __init__(self, database: SqliteDatabase) -> None:
        self.database = database

    def enqueue(self, event_id: str, priority: float) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO ai_analysis_queue
                   (news_event_id, priority, status, attempts, available_at)
                   VALUES (?, ?, 'PENDING', 0, CURRENT_TIMESTAMP)
                   ON CONFLICT(news_event_id) DO UPDATE SET
                     priority = MAX(ai_analysis_queue.priority, excluded.priority),
                     status = CASE
                         WHEN ai_analysis_queue.status = 'COMPLETED' THEN ai_analysis_queue.status
                         ELSE 'PENDING'
                     END
                """,
                (event_id, priority),
            )

    def list_due(self, limit: int = 5) -> list[str]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """SELECT news_event_id
                   FROM ai_analysis_queue
                   WHERE status IN ('PENDING', 'FAILED')
                     AND available_at <= CURRENT_TIMESTAMP
                   ORDER BY priority DESC, available_at ASC, id ASC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [str(row["news_event_id"]) for row in rows]

    def mark_processing(self, event_id: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """UPDATE ai_analysis_queue
                   SET status = 'PROCESSING',
                       attempts = attempts + 1,
                       last_error = NULL
                   WHERE news_event_id = ?
                     AND status IN ('PENDING', 'FAILED')""",
                (event_id,),
            )

    def mark_completed(self, event_id: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """UPDATE ai_analysis_queue
                   SET status = 'COMPLETED',
                       processed_at = CURRENT_TIMESTAMP,
                       last_error = NULL
                   WHERE news_event_id = ?""",
                (event_id,),
            )

    def mark_failed(self, event_id: str, error: str, retry_after_seconds: int = 60) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """UPDATE ai_analysis_queue
                   SET status = 'FAILED',
                       last_error = ?,
                       available_at = datetime('now', '+' || ? || ' seconds')
                   WHERE news_event_id = ?""",
                (error[:2000], retry_after_seconds, event_id),
            )

    def pending_count(self) -> int:
        with self.database.connect() as connection:
            row = connection.execute(
                """SELECT COUNT(*) AS count
                   FROM ai_analysis_queue
                   WHERE status IN ('PENDING', 'FAILED')"""
            ).fetchone()
        return int(row["count"])

    def status(self, event_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM ai_analysis_queue WHERE news_event_id = ?",
                (event_id,),
            ).fetchone()
        return dict(row) if row is not None else None


class MarketKnowledgeRepository:
    """Stores AI-derived market context for retrieval in later sessions."""

    def __init__(self, database: SqliteDatabase) -> None:
        self.database = database

    def save(self, event: NewsEvent, decision: AiDecision, keywords: list[str]) -> None:
        created_at = datetime.now(timezone.utc).isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO market_knowledge
                   (news_event_id, symbols_json, keywords_json, signal, confidence,
                    knowledge_text, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(news_event_id) DO UPDATE SET
                     symbols_json = excluded.symbols_json,
                     keywords_json = excluded.keywords_json,
                     signal = excluded.signal,
                     confidence = excluded.confidence,
                     knowledge_text = excluded.knowledge_text,
                     created_at = excluded.created_at""",
                (
                    event.id,
                    json.dumps(event.symbols),
                    json.dumps(keywords),
                    decision.signal.value,
                    decision.confidence,
                    decision.reasoning,
                    created_at,
                ),
            )

    def list_recent(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM market_knowledge
                   ORDER BY created_at DESC, id DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
