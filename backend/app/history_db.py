import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.environ.get(
    "EDGELEGAL_HISTORY_DB",
    os.path.join(os.path.dirname(__file__), "..", "edgelegal_history.sqlite3"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    page_count INTEGER
);
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    hypothesis TEXT NOT NULL,
    label TEXT NOT NULL,
    confidence REAL,
    source TEXT CHECK (source IN ('classifier', 'llm')),
    created_at TEXT NOT NULL,
    report_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analyses_document_id ON analyses(document_id);
"""

# Documents uploaded before history existed have no stored filename.
UNKNOWN_FILENAME = "(uploaded before history was enabled)"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_timestamp(value: str) -> str:
    """Parse any ISO-8601 timestamp and return it in the stored UTC format."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def record_document(doc_id: str, filename: str, page_count: Optional[int]) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO documents (id, filename, uploaded_at, page_count) VALUES (?, ?, ?, ?)",
            (doc_id, filename, utc_now(), page_count),
        )


def record_analysis(doc_id: str, hypothesis: str, report: dict) -> int:
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO documents (id, filename, uploaded_at, page_count) VALUES (?, ?, ?, NULL)",
            (doc_id, UNKNOWN_FILENAME, utc_now()),
        )
        cursor = conn.execute(
            """INSERT INTO analyses
               (document_id, hypothesis, label, confidence, source, created_at, report_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                doc_id,
                hypothesis,
                report["label"],
                report.get("confidence"),
                report.get("source"),
                utc_now(),
                json.dumps(report),
            ),
        )
        return cursor.lastrowid


def list_analyses(
    limit: int,
    offset: int,
    label: Optional[str] = None,
    document_id: Optional[str] = None,
    q: Optional[str] = None,
    since: Optional[str] = None,
) -> tuple[list[dict], int]:
    where, params = [], []
    if label:
        where.append("a.label = ?")
        params.append(label)
    if document_id:
        where.append("a.document_id = ?")
        params.append(document_id)
    if q:
        where.append("(a.hypothesis LIKE ? ESCAPE '\\' OR d.filename LIKE ? ESCAPE '\\')")
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params += [f"%{escaped}%", f"%{escaped}%"]
    if since:
        where.append("a.created_at >= ?")
        params.append(normalize_timestamp(since))
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    base = f"FROM analyses a JOIN documents d ON d.id = a.document_id {where_sql}"
    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
        rows = conn.execute(
            f"""SELECT a.id, a.document_id, d.filename, a.hypothesis, a.label,
                       a.confidence, a.source, a.created_at
                {base}
                ORDER BY a.created_at DESC, a.id DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()
    return [dict(r) for r in rows], total


def get_analysis(analysis_id: int) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(
            "SELECT report_json FROM analyses WHERE id = ?", (analysis_id,)
        ).fetchone()
    return json.loads(row["report_json"]) if row else None


def get_analytics() -> dict:
    with connect() as conn:
        totals = conn.execute(
            """SELECT COUNT(DISTINCT document_id) AS documents_analyzed,
                      COUNT(*) AS total_analyses,
                      SUM(CASE WHEN label = 'Contradiction' THEN 1 ELSE 0 END) AS contradictions,
                      AVG(CASE WHEN source = 'classifier' THEN confidence END) AS avg_confidence,
                      SUM(CASE WHEN source = 'classifier' THEN 1 ELSE 0 END) AS classifier_count,
                      SUM(CASE WHEN source = 'llm' THEN 1 ELSE 0 END) AS llm_count
               FROM analyses"""
        ).fetchone()
        top_hypotheses = conn.execute(
            """SELECT hypothesis,
                      COUNT(*) AS contradiction_count
               FROM analyses
               WHERE label = 'Contradiction'
               GROUP BY hypothesis
               ORDER BY contradiction_count DESC, hypothesis
               LIMIT 5"""
        ).fetchall()

    total_analyses = totals["total_analyses"] or 0
    contradictions = totals["contradictions"] or 0

    return {
        "documents_analyzed": totals["documents_analyzed"] or 0,
        "total_analyses": total_analyses,
        "total_contradictions": contradictions,
        "contradiction_rate": (contradictions / total_analyses) if total_analyses else 0.0,
        "top_hypotheses": [
            {"hypothesis": r["hypothesis"], "contradiction_count": r["contradiction_count"]}
            for r in top_hypotheses
        ],
        "avg_classifier_confidence": totals["avg_confidence"],
        "classifier_count": totals["classifier_count"] or 0,
        "llm_count": totals["llm_count"] or 0,
    }


def list_documents() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT d.id, d.filename, d.uploaded_at, d.page_count,
                      COUNT(a.id) AS analysis_count
               FROM documents d JOIN analyses a ON a.document_id = d.id
               GROUP BY d.id
               ORDER BY MAX(a.created_at) DESC"""
        ).fetchall()
    return [dict(r) for r in rows]
