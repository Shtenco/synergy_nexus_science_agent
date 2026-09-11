from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from .contracts import SourceRecord


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    source_id TEXT PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    content_sha256 TEXT NOT NULL UNIQUE,
    retrieved_at TEXT NOT NULL,
    published_at TEXT,
    source_type TEXT NOT NULL,
    domain TEXT NOT NULL,
    lineage_id TEXT NOT NULL,
    is_primary INTEGER NOT NULL,
    quality_score REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_lineage ON documents(lineage_id);
CREATE INDEX IF NOT EXISTS idx_documents_published ON documents(published_at);
CREATE INDEX IF NOT EXISTS idx_documents_quality ON documents(quality_score);
"""


class ResearchIndex:
    """Persistent content-addressed store with optional SQLite FTS5 search."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self._fts = self._ensure_fts()

    def _ensure_fts(self) -> bool:
        try:
            self.db.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(source_id UNINDEXED, title, text)"
            )
            return True
        except sqlite3.OperationalError:
            return False

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "ResearchIndex":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def add(self, source: SourceRecord) -> bool:
        try:
            self.db.execute(
                """
                INSERT INTO documents(
                    source_id,url,title,text,content_sha256,retrieved_at,published_at,
                    source_type,domain,lineage_id,is_primary,quality_score
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    source.source_id, source.url, source.title, source.text,
                    source.content_sha256, source.retrieved_at, source.published_at,
                    source.source_type, source.domain, source.lineage_id,
                    1 if source.is_primary else 0, float(source.quality_score),
                ),
            )
        except sqlite3.IntegrityError:
            return False
        if self._fts:
            self.db.execute(
                "INSERT INTO documents_fts(source_id,title,text) VALUES(?,?,?)",
                (source.source_id, source.title, source.text),
            )
        self.db.commit()
        return True

    @staticmethod
    def _row_to_source(row: sqlite3.Row) -> SourceRecord:
        return SourceRecord(
            source_id=row["source_id"],
            url=row["url"],
            title=row["title"],
            text=row["text"],
            content_sha256=row["content_sha256"],
            retrieved_at=row["retrieved_at"],
            published_at=row["published_at"],
            source_type=row["source_type"],
            domain=row["domain"],
            lineage_id=row["lineage_id"],
            is_primary=bool(row["is_primary"]),
            quality_score=float(row["quality_score"]),
        )

    def search(self, query: str, *, limit: int = 20, min_quality: float = 0.0) -> List[SourceRecord]:
        limit = max(1, min(int(limit), 500))
        if self._fts:
            rows = self.db.execute(
                """
                SELECT d.*
                FROM documents_fts f
                JOIN documents d ON d.source_id=f.source_id
                WHERE documents_fts MATCH ? AND d.quality_score >= ?
                ORDER BY bm25(documents_fts), d.quality_score DESC
                LIMIT ?
                """,
                (query, float(min_quality), limit),
            ).fetchall()
        else:
            needle = f"%{query}%"
            rows = self.db.execute(
                """
                SELECT * FROM documents
                WHERE quality_score >= ? AND (title LIKE ? OR text LIKE ?)
                ORDER BY quality_score DESC
                LIMIT ?
                """,
                (float(min_quality), needle, needle, limit),
            ).fetchall()
        return [self._row_to_source(row) for row in rows]

    def by_lineage(self, lineage_id: str, *, limit: int = 100) -> List[SourceRecord]:
        rows = self.db.execute(
            "SELECT * FROM documents WHERE lineage_id=? ORDER BY quality_score DESC LIMIT ?",
            (lineage_id, max(1, int(limit))),
        ).fetchall()
        return [self._row_to_source(row) for row in rows]

    def count(self) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM documents").fetchone()[0])

    def manifest(self) -> dict[str, str]:
        rows = self.db.execute("SELECT source_id,content_sha256 FROM documents ORDER BY source_id").fetchall()
        return {row["source_id"]: row["content_sha256"] for row in rows}

    def export_manifest(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.manifest(), ensure_ascii=False, indent=2), encoding="utf-8")
