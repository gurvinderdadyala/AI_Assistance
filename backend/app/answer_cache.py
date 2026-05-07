import json
import sqlite3
import time
from pathlib import Path

from app.models import Source


class AnswerCache:
    def __init__(self, db_path: Path, ttl_seconds: int):
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def get(self, cache_key: str) -> tuple[str, list[Source]] | None:
        self._delete_expired()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT answer, sources_json FROM answer_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        sources = [Source(**source) for source in json.loads(row["sources_json"])]
        return str(row["answer"]), sources

    def set(self, cache_key: str, question: str, answer: str, sources: list[Source]) -> None:
        now = int(time.time())
        sources_json = json.dumps([source.model_dump() for source in sources])
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO answer_cache (cache_key, question, answer, sources_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    question = excluded.question,
                    answer = excluded.answer,
                    sources_json = excluded.sources_json,
                    created_at = excluded.created_at
                """,
                (cache_key, question, answer, sources_json, now),
            )

    def clear(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM answer_cache")

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS answer_cache (
                    cache_key TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    sources_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_answer_cache_created_at ON answer_cache(created_at)"
            )

    def _delete_expired(self) -> None:
        if self.ttl_seconds <= 0:
            return
        expires_before = int(time.time()) - self.ttl_seconds
        with self._connect() as connection:
            connection.execute("DELETE FROM answer_cache WHERE created_at < ?", (expires_before,))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        return connection
