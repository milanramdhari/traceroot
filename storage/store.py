import json
import os
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone

from tracing.trace import Trace

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TRACES_DIR = os.path.join(_ROOT, "storage", "traces")
_ANALYSES_DIR = os.path.join(_ROOT, "storage", "analyses")
_DB_PATH = os.path.join(_ROOT, "storage", "index.db")


def _ensure_dirs():
    os.makedirs(_TRACES_DIR, exist_ok=True)


def _ensure_analyses_dir():
    os.makedirs(_ANALYSES_DIR, exist_ok=True)


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS traces (
            trace_id  TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            status    TEXT NOT NULL,
            final_score REAL,
            file_path TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            trace_id         TEXT PRIMARY KEY,
            analyzed_at      TEXT NOT NULL,
            failure_type     TEXT NOT NULL,
            root_cause_step  TEXT NOT NULL,
            file_path        TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _avg_confidence(trace: Trace):
    scores = [s.confidence for s in trace.spans if s.confidence is not None]
    return round(sum(scores) / len(scores), 2) if scores else None


def save_trace(trace: Trace) -> str:
    """Write trace to JSON and index it in SQLite. Returns the JSON file path."""
    _ensure_dirs()

    file_path = os.path.join(_TRACES_DIR, f"{trace.trace_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(asdict(trace), f, indent=2, default=str)

    conn = _get_db()
    conn.execute(
        """
        INSERT OR REPLACE INTO traces (trace_id, timestamp, status, final_score, file_path)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            trace.trace_id,
            trace.started_at,
            trace.status,
            _avg_confidence(trace),
            file_path,
        ),
    )
    conn.commit()
    conn.close()

    return file_path


def save_analysis(analysis_dict: dict) -> str:
    """
    Write a FailureAnalysis (as dict, e.g. from dataclasses.asdict) to JSON
    and index it in SQLite. Returns the JSON file path.
    """
    _ensure_analyses_dir()
    trace_id = analysis_dict["trace_id"]
    file_path = os.path.join(_ANALYSES_DIR, f"{trace_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(analysis_dict, f, indent=2, default=str)

    conn = _get_db()
    conn.execute(
        """
        INSERT OR REPLACE INTO analyses
            (trace_id, analyzed_at, failure_type, root_cause_step, file_path)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            trace_id,
            datetime.now(timezone.utc).isoformat(),
            analysis_dict.get("failure_type", ""),
            analysis_dict.get("root_cause_step", ""),
            file_path,
        ),
    )
    conn.commit()
    conn.close()
    return file_path
