"""
Token vault: maps masked tokens back to their original sensitive values so
the response can be safely rehydrated for the internal, authorized user
after the round trip to the external LLM.

Backed by SQLite (in-memory per process for this demo). In production this
is a proper encrypted, access-controlled key-value store (e.g. a Vault/KMS-backed
table) with per-session TTLs and audit logging on every read.
"""
import sqlite3
import threading

_lock = threading.Lock()
_conn = sqlite3.connect(":memory:", check_same_thread=False)
_conn.execute(
    """
    CREATE TABLE IF NOT EXISTS vault (
        session_id TEXT NOT NULL,
        token TEXT NOT NULL,
        original_value TEXT NOT NULL,
        label TEXT NOT NULL,
        PRIMARY KEY (session_id, token)
    )
    """
)
_conn.commit()


def store(session_id: str, token: str, original_value: str, label: str) -> None:
    with _lock:
        _conn.execute(
            "INSERT OR REPLACE INTO vault (session_id, token, original_value, label) VALUES (?, ?, ?, ?)",
            (session_id, token, original_value, label),
        )
        _conn.commit()


def resolve(session_id: str, token: str) -> str | None:
    with _lock:
        row = _conn.execute(
            "SELECT original_value FROM vault WHERE session_id = ? AND token = ?",
            (session_id, token),
        ).fetchone()
    return row[0] if row else None


def all_entries(session_id: str) -> list[tuple[str, str, str]]:
    with _lock:
        rows = _conn.execute(
            "SELECT token, original_value, label FROM vault WHERE session_id = ? ORDER BY rowid",
            (session_id,),
        ).fetchall()
    return rows


def clear_session(session_id: str) -> None:
    with _lock:
        _conn.execute("DELETE FROM vault WHERE session_id = ?", (session_id,))
        _conn.commit()
