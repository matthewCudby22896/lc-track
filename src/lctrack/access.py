import datetime
import json
import sqlite3

import keyring

from .constants import (
    DB_LOC,
    DEFAULT_STUDY_MODE,
    LOCAL_EVENT_LOG_LOC,
    PROBLEM_SET_F_LOC,
    FrontendID,
    ProblemSlug,
    ProblemTitle,
    StudyMode,
    TopicSlug,
    TopicText,
)
from .ds import AddEntryEvent, BaseEvent, Entry, Problem, RmEntryEvent


def get_db_connection() -> sqlite3.Connection:
    con = sqlite3.connect(
        DB_LOC,
        autocommit=False,
        isolation_level=None # Disables opening transactions implicitly
    )
    con.execute("PRAGMA foreign_keys = ON;")

    return con


# TABLE : problems

def get_for_review_problems(con : sqlite3.Connection) -> list[Problem]:
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

def get_active_problems(con : sqlite3.Connection) -> list[Problem]:
    cur = con.cursor()
    try:
        cur.execute("SELECT * FROM problems WHERE active = 1")

        active = [Problem.from_row(x) for x in cur.fetchall()]
    finally:
        cur.close()

    return active

def update_SM2_state(con : sqlite3.Connection,
                     problem_slug : ProblemSlug,
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
            WHERE slug = ?
        """, (n, ef, i, int(last_review_ts), int(next_review_ts), problem_slug))
    finally:
        cur.close()

def bulk_update_problem_state(
        con : sqlite3.Connection,
        new_states : list[tuple[int, float, int, int, int, ProblemSlug]]) -> None:
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
            WHERE slug = ?
        """, new_states)
    finally:
        cur.close()

def set_active(con :sqlite3.Connection, ui_id : int, active: bool) -> None:
    cur = con.cursor()
    try:
        cur.execute(
            "UPDATE problems SET active = ? WHERE ui_id = ?",
            (active, ui_id)
        )
    finally:
        cur.close()

def bulk_set_active_by_slug(con : sqlite3.Connection, slugs : list[str], active: bool) -> None:
    cur = con.cursor()
    try:
        cur.executemany(
            "UPDATE problems SET active = ? WHERE slug = ?",
            [(active, slug) for slug in slugs]
        )
    finally:
        cur.close()

def get_problem_by_id(con: sqlite3.Connection, problem_id: FrontendID) -> Problem | None:
    cur = con.cursor()
    try:
        cur.execute(
            """
            SELECT
                slug,
                ui_id,
                title,
                difficulty,
                last_review_at,
                next_review_at,
                EF,
                I,
                n,
                active
            FROM problems
            WHERE ui_id = ?
            """,
            (problem_id,)
        )
        row = cur.fetchone()
    finally:
        cur.close()

    return Problem.from_row(row) if row else None

def get_problem_by_slug(con: sqlite3.Connection, problem_slug: ProblemSlug) -> Problem | None:
    cur = con.cursor()
    try:
        cur.execute(
            """
            SELECT
                slug,
                ui_id,
                title,
                difficulty,
                last_review_at,
                next_review_at,
                EF,
                I,
                n,
                active
            FROM problems
            WHERE ui_id = ?
            """,
            (problem_slug,)
        )
        row = cur.fetchone()
    finally:
        cur.close()

    return Problem.from_row(row) if row else None

def get_problem_topics(con : sqlite3.Connection, problem_slug : ProblemSlug) -> list[str]:
    cur = con.cursor()
    try:
        print(problem_slug)
        cur.execute("""
            SELECT t.topic_title
            FROM problem_topic pt
            JOIN topics t ON pt.topic_slug = t.topic_slug
            WHERE pt.problem_slug = ?
        """, (problem_slug,))

        topics = [x[0] for  x in cur.fetchall()]

        print(topics)

        return topics

    finally:
        cur.close()

# EVENT LOGGING

def append_event(event : BaseEvent) -> None:
    with open(LOCAL_EVENT_LOG_LOC, "a", encoding="utf-8") as f:
        json_event = json.dumps(event.to_dict())
        f.write(json_event + '\n')

def process_event(con : sqlite3.Connection, event : BaseEvent) -> None:
    match event:
        case AddEntryEvent():
            add_entry(
                con,
                Entry(
                    event.problem_slug,
                    event.confidence,
                    event.ts,
                    event.entry_uuid
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
            INSERT INTO entries (uuid, problem_slug, confidence, ts)
            VALUES (?, ?, ?, ?)
            """,
            entry.to_row()
        )
    finally:
        cur.close()

def get_entry(con : sqlite3.Connection, entry_uuid : str) -> Entry | None:
    cur = con.cursor()
    try:
        cur.execute("""
            SELECT uuid, problem_slug, confidence, ts
            FROM entries
            WHERE uuid = ?
        """, (entry_uuid,))

        row : tuple[str, ProblemSlug, int, int] | None = cur.fetchone()
    finally:
        cur.close()

    return Entry.from_row(row) if row else None

def get_all_entries(con : sqlite3.Connection) -> list[Entry]:
    cur = con.cursor()
    try:
        cur.execute("SELECT uuid, problem_slug, confidence, ts FROM entries")

        return [Entry.from_row(row) for row in cur.fetchall()]
    finally:
        cur.close()

def get_entries_by_problem_slug(con : sqlite3.Connection, problem_slug : str) -> list[Entry]:
    cur = con.cursor()
    try:
        cur.execute("SELECT uuid, problem_slug, confidence, ts FROM entries WHERE problem_slug = ?", (problem_slug,))
        entries : list[Entry] = [Entry.from_row(row) for row in cur.fetchall()]
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

def get_state(con : sqlite3.Connection, key : str) -> str | None:
    cur = con.cursor()
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

def get_study_mode(con : sqlite3.Connection) -> StudyMode:
    mode_str = get_state(con, 'study_mode')

    if mode_str is None:
        return DEFAULT_STUDY_MODE

    return StudyMode(mode_str)

def set_pat(pat : str) -> None:
    keyring.set_password("lc-track", "gh_pat", pat)

def get_pat() -> str | None:
    return keyring.get_password("lc-track", "gh_pat")

def populate_db_with_problem_set(con : sqlite3.Connection,
                                 problems : list[tuple[ProblemSlug, FrontendID, ProblemTitle, int]],
                                 topics : list[tuple[TopicSlug, TopicText]],
                                 problem_topics : list[tuple[ProblemSlug, TopicSlug]]) -> None:
    cur = con.cursor()
    try:
        stmt = "INSERT INTO problems (slug, ui_id, title, difficulty) VALUES (?, ?, ?, ?);"
        cur.executemany(stmt, problems)

        stmt = "INSERT INTO topics (topic_slug, topic_title) VALUES (?, ?);"
        cur.executemany(stmt, topics)

        stmt = "INSERT INTO problem_topic (problem_slug, topic_slug) VALUES (?, ?);"
        cur.executemany(stmt, problem_topics)
    finally:
        cur.close()

def bootstap_db(con : sqlite3.Connection) -> None:
    stmt = """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT UNIQUE NOT NULL,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    cur = con.cursor()
    try:
        cur.execute(stmt)
    finally:
        cur.close()

def get_applied_migrations(con: sqlite3.Connection) -> set[str]:
    stmt = """
    SELECT filename
    FROM schema_migrations;
    """
    cur = con.cursor()
    try:
        cur.execute(stmt)
        return {row[0] for row in cur.fetchall()}
    finally:
        cur.close()

def record_migration(con: sqlite3.Connection, filename: str) -> None:
    stmt = """
    INSERT INTO schema_migrations (filename)
    VALUES (?);
    """
    cur = con.cursor()
    try:
        cur.execute(stmt, (filename,))
    finally:
        cur.close()

def load_problem_sets() -> dict[str, list[str]]:
    with open(PROBLEM_SET_F_LOC) as f:
        # Cast the result so mypy treats it as the correct type
        problem_sets: dict[str, list[str]] = json.load(f)

    return problem_sets
