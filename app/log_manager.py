import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path.home() / "Library" / "Application Support" / "MonitorQS" / "qs_logbuch.db"


def _get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pruefungen (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                zeitstempel TEXT NOT NULL,
                monitor     TEXT NOT NULL,
                testbild    TEXT NOT NULL,
                pruefer     TEXT NOT NULL,
                ergebnis    TEXT NOT NULL,
                kommentar   TEXT
            )
        """)
        # Migration: add testbild column if missing (old schema)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(pruefungen)").fetchall()}
        if "testbild" not in cols:
            conn.execute("ALTER TABLE pruefungen ADD COLUMN testbild TEXT NOT NULL DEFAULT ''")
        # Migration: Einzelkriterien (JSON-Liste) der Konstanzprüfung nach BAG-Wegleitung Tabelle C
        if "kriterien" not in cols:
            conn.execute("ALTER TABLE pruefungen ADD COLUMN kriterien TEXT")
        # Migration: an welchem Bildschirm tatsächlich geprüft wurde (Name + Pixel), fürs Audit
        if "bildschirm" not in cols:
            conn.execute("ALTER TABLE pruefungen ADD COLUMN bildschirm TEXT")


def log_pruefung(monitor: str, testbild: str, pruefer: str, ergebnis: str, kommentar: str = "",
                 kriterien: list | None = None, bildschirm: str = ""):
    zeitstempel = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kriterien_json = None
    if kriterien:
        kriterien_json = json.dumps(
            [{"id": k["id"], "kurz": k["kurz"], "text": k.get("text", ""), "testbild": k.get("testbild", ""), "erfuellt": bool(k["erfuellt"])}
             for k in kriterien],
            ensure_ascii=False,
        )
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO pruefungen (zeitstempel, monitor, testbild, pruefer, ergebnis, kommentar, kriterien, bildschirm) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (zeitstempel, monitor, testbild, pruefer, ergebnis, kommentar, kriterien_json, bildschirm or None)
        )
    return zeitstempel


def get_pruefungen(von: str = None, bis: str = None) -> list:
    query = "SELECT * FROM pruefungen"
    params = []
    if von and bis:
        query += " WHERE zeitstempel >= ? AND zeitstempel <= ?"
        params = [von, bis + " 23:59:59"]
    elif von:
        query += " WHERE zeitstempel >= ?"
        params = [von]
    query += " ORDER BY zeitstempel ASC"
    with _get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["kriterien"] = json.loads(d["kriterien"]) if d.get("kriterien") else []
        result.append(d)
    return result


def hat_pruefung_diese_woche() -> bool:
    """True, wenn seit Montag 00:00 der laufenden Woche mind. eine Prüfung erfasst wurde."""
    today = datetime.now()
    week_start = (today - timedelta(days=today.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0)
    with _get_conn() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM pruefungen WHERE zeitstempel >= ?",
            (week_start.strftime("%Y-%m-%d %H:%M:%S"),)
        ).fetchone()[0]
    return n > 0


def get_jahre() -> list[int]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT DISTINCT substr(zeitstempel,1,4) as jahr FROM pruefungen ORDER BY jahr DESC").fetchall()
    return [int(r["jahr"]) for r in rows]
