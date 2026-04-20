"""
database/db.py
Gestionează conexiunea SQLite și operațiile cu baza de date.
"""

import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "sen_data.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Creează tabelele dacă nu există."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                carbune     REAL,
                hidrocarburi REAL,
                hidro       REAL,
                nuclear     REAL,
                eolian      REAL,
                fotovoltaic REAL,
                biomasa     REAL,
                stocare     REAL,
                consum      REAL,
                productie   REAL,
                sold        REAL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON readings(timestamp)
        """)
        conn.commit()


def insert_reading(data: dict):
    """Inserează o citire nouă."""
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO readings
                (timestamp, carbune, hidrocarburi, hidro, nuclear,
                 eolian, fotovoltaic, biomasa, stocare, consum, productie, sold)
            VALUES
                (:timestamp, :carbune, :hidrocarburi, :hidro, :nuclear,
                 :eolian, :fotovoltaic, :biomasa, :stocare, :consum, :productie, :sold)
        """, data)
        conn.commit()


def get_latest():
    """Returnează ultima citire."""
    with get_conn() as conn:
        row = conn.execute("""
            SELECT * FROM readings ORDER BY timestamp DESC LIMIT 1
        """).fetchone()
    return dict(row) if row else None


def get_history_aggregated(minutes: int = 15):
    """
    Returnează ultimele N minute agregate pe minut.
    Pentru fiecare minut: ultima citire din acel minut (cea mai recentă).
    Dacă într-un minut nu există citire → nu apare în rezultat (nu inserăm null-uri artificiale).
    """
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                strftime('%Y-%m-%dT%H:%M', timestamp) AS minute,
                timestamp,
                carbune, hidrocarburi, hidro, nuclear,
                eolian, fotovoltaic, biomasa, stocare,
                consum, productie, sold
            FROM readings
            WHERE timestamp >= datetime('now', :offset)
            GROUP BY minute
            HAVING timestamp = MAX(timestamp)
            ORDER BY minute DESC
            LIMIT :limit
        """, {
            "offset": f"-{minutes} minutes",
            "limit": minutes
        }).fetchall()
    return [dict(r) for r in rows]


def get_raw_recent(limit: int = 50):
    """Ultimele N citiri brute."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM readings ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_last_sync_time():
    """Timestamp-ul ultimei citiri salvate."""
    with get_conn() as conn:
        row = conn.execute("""
            SELECT timestamp FROM readings ORDER BY timestamp DESC LIMIT 1
        """).fetchone()
    return row["timestamp"] if row else None
