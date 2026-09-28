"""Transactional durable state and hash-linked history, not a WORM storage claim."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .common import digest, encoded, loads, require


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.tx() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS meta(version INTEGER NOT NULL);
                INSERT INTO meta SELECT 1 WHERE NOT EXISTS(SELECT 1 FROM meta);
                CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS artifacts(sha TEXT PRIMARY KEY, run TEXT NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS invocations(id TEXT PRIMARY KEY, sha TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, run TEXT NOT NULL, value TEXT NOT NULL, previous TEXT NOT NULL, sha TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS help(id TEXT PRIMARY KEY, run TEXT NOT NULL, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS schedules(id TEXT PRIMARY KEY, run TEXT NOT NULL UNIQUE, value TEXT NOT NULL);
            ''')
            require(db.execute("SELECT version FROM meta").fetchone()[0] == 1, "state migration requires reviewed migration; unsupported schema")

    @contextmanager
    def tx(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def run(self, db, run_id):
        row = db.execute("SELECT value FROM runs WHERE id=?", (run_id,)).fetchone()
        require(row is not None, "unknown run")
        return loads(row[0])

    def save(self, db, run):
        db.execute("UPDATE runs SET value=? WHERE id=?", (encoded(run).decode(), run["id"]))

    def event(self, db, run_id, event):
        previous = db.execute("SELECT sha FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        previous = previous[0] if previous else "0" * 64
        sha = digest({"run": run_id, "previous": previous, "event": event})
        db.execute("INSERT INTO events(run,value,previous,sha) VALUES(?,?,?,?)",
                   (run_id, encoded(event).decode(), previous, sha))
        return sha

    def artifact(self, db, run_id, kind, value):
        sha = digest(value)
        db.execute("INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?)", (sha, run_id, kind, encoded(value).decode()))
        return sha

    def verify_chain(self, db):
        previous = "0" * 64
        for row in db.execute("SELECT * FROM events ORDER BY seq"):
            require(row["previous"] == previous and row["sha"] == digest({"run": row["run"], "previous": previous, "event": loads(row["value"])}), "history integrity failure")
            previous = row["sha"]
        for row in db.execute("SELECT sha,value FROM artifacts"):
            require(digest(loads(row["value"])) == row["sha"], "artifact integrity failure")
        return previous

    def artifacts(self, db, run_id, kind):
        return [(r["sha"], loads(r["value"])) for r in db.execute("SELECT sha,value FROM artifacts WHERE run=? AND kind=? ORDER BY rowid", (run_id, kind))]
