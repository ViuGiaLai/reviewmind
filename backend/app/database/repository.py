from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from app.review.models import ReviewResult


class ReviewRepository:
    """Local SQLite adapter. The engine does not depend on this class."""

    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS review_sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    filename TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    result_json TEXT NOT NULL
                )
            """)

    def save(self, filename: str, result: ReviewResult) -> str:
        session_id = str(uuid4())
        payload = json.dumps(asdict(result), ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO review_sessions (id, filename, profile_id, score, summary, result_json) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, filename, result.profile_id, result.score, result.summary, payload),
            )
        return session_id

    def list(self, limit: int = 30) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT id, created_at, filename, profile_id, score, summary FROM review_sessions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def get(self, session_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM review_sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["result"] = json.loads(data.pop("result_json"))
