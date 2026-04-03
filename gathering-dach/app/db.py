"""
SQLite state store — completely standalone.
Stores pipeline state, phase1 companies, phase2 contacts.
"""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path("/data/state.db")


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                id          INTEGER PRIMARY KEY,
                project_id  INTEGER NOT NULL DEFAULT 9,
                state       TEXT NOT NULL DEFAULT 'idle',
                phase1_filters TEXT,
                phase2_filters TEXT,
                started_at  TEXT,
                updated_at  TEXT,
                notes       TEXT
            );

            CREATE TABLE IF NOT EXISTS companies (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id      INTEGER NOT NULL,
                domain      TEXT NOT NULL,
                name        TEXT,
                hq_country  TEXT,
                employees   INTEGER,
                industry    TEXT,
                latam_countries TEXT,
                latam_count INTEGER DEFAULT 0,
                approved    INTEGER DEFAULT 1,
                UNIQUE(run_id, domain)
            );

            CREATE TABLE IF NOT EXISTS contacts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id      INTEGER NOT NULL,
                company_domain TEXT NOT NULL,
                first_name  TEXT,
                last_name   TEXT,
                title       TEXT,
                linkedin_url TEXT,
                apollo_id   TEXT,
                UNIQUE(run_id, apollo_id)
            );
        """)


@contextmanager
def _conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_run(run_id: int) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None


def get_latest_run() -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None


def create_run(project_id: int, phase1_filters: dict, notes: str = "") -> int:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO runs (project_id, state, phase1_filters, started_at, updated_at, notes) VALUES (?,?,?,?,?,?)",
            (project_id, "phase1_running", json.dumps(phase1_filters), now, now, notes),
        )
        return cur.lastrowid


def set_run_state(run_id: int, state: str, **extra):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    sets = ["state=?", "updated_at=?"]
    vals = [state, now]
    for k, v in extra.items():
        sets.append(f"{k}=?")
        vals.append(json.dumps(v) if isinstance(v, (dict, list)) else v)
    vals.append(run_id)
    with _conn() as conn:
        conn.execute(f"UPDATE runs SET {', '.join(sets)} WHERE id=?", vals)


def upsert_company(run_id: int, domain: str, **fields):
    with _conn() as conn:
        existing = conn.execute(
            "SELECT id, latam_count, latam_countries FROM companies WHERE run_id=? AND domain=?",
            (run_id, domain),
        ).fetchone()

        if existing:
            # Merge LATAM countries
            existing_countries = set(json.loads(existing["latam_countries"] or "[]"))
            new_countries = set(json.loads(fields.get("latam_countries", "[]")))
            merged = sorted(existing_countries | new_countries)
            conn.execute(
                "UPDATE companies SET latam_countries=?, latam_count=latam_count+? WHERE id=?",
                (json.dumps(merged), fields.get("latam_count", 1), existing["id"]),
            )
        else:
            cols = ["run_id", "domain"] + list(fields.keys())
            placeholders = ",".join("?" * len(cols))
            vals = [run_id, domain] + [
                json.dumps(v) if isinstance(v, list) else v
                for v in fields.values()
            ]
            conn.execute(
                f"INSERT OR IGNORE INTO companies ({','.join(cols)}) VALUES ({placeholders})",
                vals,
            )


def get_companies(run_id: int, approved_only: bool = False) -> List[Dict[str, Any]]:
    with _conn() as conn:
        q = "SELECT * FROM companies WHERE run_id=?"
        if approved_only:
            q += " AND approved=1"
        q += " ORDER BY latam_count DESC"
        rows = conn.execute(q, (run_id,)).fetchall()
        return [dict(r) for r in rows]


def set_company_approval(run_id: int, domain: str, approved: bool):
    with _conn() as conn:
        conn.execute(
            "UPDATE companies SET approved=? WHERE run_id=? AND domain=?",
            (1 if approved else 0, run_id, domain),
        )


def upsert_contact(run_id: int, apollo_id: str, **fields):
    with _conn() as conn:
        cols = ["run_id", "apollo_id"] + list(fields.keys())
        placeholders = ",".join("?" * len(cols))
        conn.execute(
            f"INSERT OR IGNORE INTO contacts ({','.join(cols)}) VALUES ({placeholders})",
            [run_id, apollo_id] + list(fields.values()),
        )


def get_contacts(run_id: int) -> List[Dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM contacts WHERE run_id=? ORDER BY id",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def count_contacts(run_id: int) -> int:
    with _conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM contacts WHERE run_id=?", (run_id,)
        ).fetchone()[0]
