import os
import json
from re import match
import uuid
import datetime
import sqlite3
import logging
import git    
from pathlib import Path
from typing import Dict, Tuple, List, Any, Optional

from .logic import SM2
from .ds import AddEntryEvent, BaseEvent, Entry, Problem, RmEntryEvent
from .constants import DB_FILE, LOCAL_EVENT_HISTORY, BACKUP_EVENT_HISTORY, TMP_EVENT_HISTORY


DB_SCHEMA_STMT = """
CREATE TABLE IF NOT EXISTS problems (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE, 
    title TEXT,
    difficulty INTEGER CHECK (difficulty BETWEEN 0 AND 2),
    last_review_at INTEGER,
    next_review_at INTEGER DEFAULT 0,
    EF REAL DEFAULT 2.5,
    I INTEGER DEFAULT 0,
    n INTEGER DEFAULT 0,
    active BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS topics (
    topic_slug TEXT PRIMARY KEY,
    topic_title TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS problem_topic (
    problem_id INTEGER NOT NULL,
    topic_slug TEXT NOT NULL,
    PRIMARY KEY (problem_id, topic_slug),
    FOREIGN KEY (problem_id) REFERENCES problems(id) ON DELETE CASCADE,
    FOREIGN KEY (topic_slug) REFERENCES topics(topic_slug) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS entries(
    uuid TEXT PRIMARY KEY, 
    problem_id INTEGER NOT NULL,
    confidence INTEGER NOT NULL CHECK (confidence BETWEEN 0 and 5),
    ts INTEGER NOT NULL,
    FOREIGN KEY (problem_id) references problems(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY, 
    value TEXT
);
"""

def get_db_connection() -> sqlite3.Connection:
    con = sqlite3.connect(DB_FILE)
    con.execute("PRAGMA foreign_keys = ON;")
    con.isolation_level = ""
    return con


def db_exists() -> bool:
    return os.path.exists(DB_FILE)

def init_db() -> None:
    with get_db_connection() as con:
        cur = con.cursor()
        try:
            cur.executescript(DB_SCHEMA_STMT)
        finally:
            cur.close()

def check_repo(path : Path) -> bool:
    try:
        git.Repo(path)
        # If this succeeds, this is a valid repo
        return True
    except git.InvalidGitRepositoryError as exc:
        # The folder exists, but it's not a git repo
        return False
    except git.NoSuchPathError as exc:
        # The folder doesn't even exist
        return False

# TABLE : problems

def get_for_review_problems(con : sqlite3.Connection) -> List[Problem]:
    now = int(datetime.datetime.now().timestamp())
    cur = con.cursor()
    try:
        cur.execute("""
            SELECT * FROM problems
            WHERE next_review_at <= ? 
            AND active = 1
        """, (now, ))
        for_review = [Problem.from_row(x) for x in  cur.fetchall()]
    finally:
        cur.close()

    return for_review

def get_active_problems(con : sqlite3.Connection) -> List[Problem]:
    cur = con.cursor()
    try:
        cur.execute("SELECT * FROM problems WHERE active = 1")

        active = [Problem.from_row(x) for x in cur.fetchall()]
    finally:
        cur.close()

    return active

def update_SM2_state(con : sqlite3.Connection, 
                     id : int,
                     n : int,
                     ef : float,
                     i : int, 
                     last_review_ts : int,
                     next_review_ts : int) -> None:
    cur = con.cursor()
    try:
        cur.execute("""
            UPDATE problems
            SET n = ?,
                ef = ?,
                i = ?,
                last_review_at = ?,
                next_review_at = ?
            WHERE id = ?
        """, (n, ef, i, int(last_review_ts), int(next_review_ts), id))
    finally:
        cur.close()

def bulk_update_problem_state(
        con : sqlite3.Connection, 
        new_states : List[int, float, int, int, int, int]) -> None:
    """
    Bulk update problems table with problem_states

    new_states : A list of tuples, each containing
        [(n, EF, I, last_review_at, next_review_at, problem_id), ...]
    """
    cur = con.cursor()
    try:
        cur.executemany("""
            UPDATE problems 
            SET n = ?, EF = ?, I = ?, last_review_at = ?, next_review_at = ?
            WHERE id = ?
        """, new_states)
    finally:
        cur.close()

def set_active(con :sqlite3.Connection, problem_id: int, active: bool) -> None:  
    cur = con.cursor()
    try:
        cur.execute(
            "UPDATE problems SET active = ? WHERE id = ?", 
            (active, problem_id)
        )
    finally:
        cur.close()

def get_problem(con : sqlite3.Connection, problem_id: int) -> Optional[Problem]:
    cur = con.cursor()
    try:
        cur.execute("SELECT * FROM problems WHERE id = ?", (problem_id,))
        row = cur.fetchone()
    finally:
        cur.close()
    return Problem.from_row(row) if row else None

def get_problem_topics(con : sqlite3.Connection, problem_id : int) -> List[str]:
    cur = con.cursor()
    try:
        cur.execute("""
            SELECT t.topic_title
            FROM problem_topic pt
            JOIN topics t ON pt.topic_slug = t.topic_slug
            WHERE pt.problem_id = ?
        """, (problem_id,))

        return [x[0] for  x in cur.fetchall()]

    finally:
        cur.close()

# EVENT LOGGING

def append_event(event : BaseEvent) -> None:
    with open(LOCAL_EVENT_HISTORY, "a", encoding="utf-8") as f:
        json_event = json.dumps(event.to_dict())
        f.write(json_event + '\n')


def process_event(con : sqlite3.Connection, event : BaseEvent) -> None:
    match event:
        case AddEntryEvent():
            add_entry(
                con,
                Entry(
                    event.entry_uuid,
                    event.problem_id,
                    event.confidence,
                    event.ts
                )
            )
        case RmEntryEvent():
            rm_entry(
                con,
                event.target_entry_uuid
            )
        case _:
            raise Exception(f"Unknown event type: {type(event)}")

# TABLE: entries

def add_entry(con : sqlite3.Connection, entry : Entry) -> None:
    cur = con.cursor()
    try:
        cur.execute(
            """
            INSERT INTO entries (uuid, problem_id, confidence, ts)
            VALUES (?, ?, ?, ?)
            """,
            entry.to_row()
        )
    finally: 
        cur.close()

def get_entry(con : sqlite3.Connection, entry_uuid : str) -> Optional[Entry]:
    cur = con.cursor()
    try:
        cur.execute("""
            SELECT uuid, problem_id, confidence, ts  
            FROM entries
            WHERE uuid = ?
        """, (entry_uuid,))

        row : Optional[Tuple[str, int, int, int]] = cur.fetchone()
    finally:
        cur.close()

    return Entry.from_row(row) if row else None

def get_all_entries(con : sqlite3.Connection) -> List[Entry]:
    cur = con.cursor()
    try: 
        cur.execute("SELECT uuid, problem_id, confidence, ts FROM entries")

        return [Entry.from_row(row) for row in cur.fetchall()]
    finally:
        cur.close()

def get_entries_by_problem_id(con : sqlite3.Connection, problem_id : int) -> List[Entry]:
    cur = con.cursor()
    try:
        cur.execute("SELECT uuid, problem_id, confidence, ts FROM entries WHERE problem_id = ?", (problem_id,))
        entries : List[Entry] = [Entry.from_row(row) for row in cur.fetchall()]
    finally:
        cur.close()

    return entries

def rm_entry(con : sqlite3.Connection, entry_uuid : str):
    cur = con.cursor()
    try:
        cur.execute("DELETE FROM entries WHERE uuid = ?", (entry_uuid,))
    finally:
        cur.close()

def clear_entries_table(con : sqlite3.Connection) -> None:
    cur = con.cursor()
    try:
        cur.execute("DELETE FROM entries")
    finally:
        cur.close()

# TABLE : state 

def get_state(con : sqlite3.Connection, key : str) -> Optional[str]:
    try:
        cur = con.execute("SELECT value FROM app_state WHERE key = ?", (key, ))
        row = cur.fetchone()
    
        return row[0] if row else None

    finally:
        cur.close()

def set_state(con : sqlite3.Connection, key: str, value: str) -> None:
    cur = con.cursor()
    try:
        cur.execute("REPLACE INTO app_state (key, value) VALUES (?, ?)", (key, value))
    finally:
        cur.close()


    







