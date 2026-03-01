import os
import random
import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from lctrack import lc_client

from . import access
from .constants import DIFF_COLOUR, MIGRATIONS_DIR, RESET, YELLOW
from .ds import DIFF_TO_INT, AddEntryEvent, Entry, Problem, RmEntryEvent


def get_problem_to_study() -> Problem | None:
    con = access.get_db_connection()

    try:
        for_review : list[Problem] = access.get_for_review_problems(con)

        if not for_review:
            return None

        chosen = random.choice(for_review)

        return chosen
    finally:
        con.close()

def get_active_problems() -> list[Problem]:
    con = access.get_db_connection()

    try:
        problems : list[Problem] = access.get_active_problems(con)

        return problems
    finally:
        con.close()

def get_for_review_problems() -> list[Problem]:
    con = access.get_db_connection()

    try:
        problems : list[Problem] = access.get_for_review_problems(con)

        return problems
    finally:
        con.close()

def activate_problem(problem_id : int) -> Problem:
    con = access.get_db_connection()

    try:
        problem = access.get_problem(con, problem_id)

        if not problem:
            raise ProblemNotFoundError()

        if problem.active:
            raise ProblemAlreadyActiveError()

        access.set_active(con, problem_id, True)

        problem.active = True

        con.commit()

        return problem

    finally:
        con.close()

def deactivate_problem(problem_id: int) -> Problem:
    con = access.get_db_connection()

    try:
        problem = access.get_problem(con, problem_id)

        if not problem:
            raise ProblemNotFoundError()

        if not problem.active:
            raise ProblemAlreadyInactiveError()

        access.set_active(con, problem_id, False)

        problem.active = False

        con.commit()

        return problem

    finally:
        con.close()

def get_problem_and_topics(problem_id : int) -> tuple[Problem, list[str]]:
    con = access.get_db_connection()

    try:
        problem = access.get_problem(con, problem_id)

        if not problem:
            raise ProblemNotFoundError

        topics : list[str] = access.get_problem_topics(con, problem_id)

        return problem, topics

    finally:
        con.close()

# TODO: It may make sense append_event first as this is the SoT, and then
# if the commit() fails we would recalc the state for the given problem
def add_entry(problem_id : int, confidence : int) -> tuple[Problem, Entry]:
    con = access.get_db_connection()

    try:
        problem = access.get_problem(con, problem_id)

        if not problem:
            raise ProblemNotFoundError

        now_ts = int(datetime.now().timestamp())

        n, ef, i, next_review_ts = calculate_new_state(
            problem.n,
            problem.ef,
            problem.i,
            confidence,
            now_ts,
        )

        entry = Entry(problem_id, confidence, now_ts)

        access.add_entry(con, entry)

        access.update_SM2_state(
            con,
            problem.id,
            n,
            ef,
            i,
            now_ts,
            next_review_ts,
        )

        access.append_event(
            AddEntryEvent(
                ts=now_ts,
                entry_uuid=entry.uuid,
                problem_id=problem.id,
                confidence=confidence
            )
        )

        # Get updated state of problem
        problem = access.get_problem(con, problem.id)

        con.commit()

        assert problem is not None

        return problem, entry

    finally:
        con.close()

def rm_entry(entry_uuid : str) -> int:
    con = access.get_db_connection()

    try:
        entry : Entry | None = access.get_entry(con, entry_uuid)

        if not entry:
            raise EntryNotNoundError

        access.rm_entry(con, entry_uuid)

        recalc_problem_state(con, entry.problem_id)

        con.commit()

        access.append_event(
            RmEntryEvent(
                ts=int(datetime.now().timestamp()),
                target_entry_uuid=entry.uuid
            )
        )

        return entry.problem_id

    finally:
        con.close()

def build_entry_log() -> str:
    con = access.get_db_connection()

    try:
        entries : list[Entry] = access.get_all_entries(con)

        if not entries:
            return "No entries found :("

        entries.sort(key = lambda x : x.ts, reverse=True)

        text_blocks = []
        for entry in entries:
            w = 12
            problem = access.get_problem(con, entry.problem_id)
            assert problem
            block = (
                f"{YELLOW}entry {entry.uuid}{RESET}\n"
                f"{'Problem:':<{w}} {entry.problem_id}. {problem.title} [{DIFF_COLOUR[problem.difficulty_txt]}{problem.difficulty_txt}{RESET}]\n"
                f"{'Date:':<{w}} {entry.timestamp_txt}\n"
                f"{'Confidence:':<{w}} {entry.confidence}/5\n"
            )
            text_blocks.append(block)

        text = "\n".join(text_blocks)

        return text

    finally:
        con.close()

def get_repo_name() -> None | str:
    con = access.get_db_connection()

    try:
        return access.get_state(con, 'BACKUP_REPO_NAME')
    finally:
        con.close()

def get_state(key : str) -> None | str:
    con = access.get_db_connection()
    try:
        return access.get_state(con, key)
    finally:
        con.close()

def get_user() -> None | str:
    con = access.get_db_connection()

    try:
        return access.get_state(con, 'USER')
    finally:
        con.close()

def recalc_problem_state(con : sqlite3.Connection, problem_id : int) -> None:
    entries : list[Entry] = access.get_entries_by_problem_id(con, problem_id)

    n, ef, i = 0, 2.5, 0

    if not entries:
        last_review_ts, next_review_ts = 0, 0
    else:
        entries.sort(key = lambda x : x.ts)
        for entry in entries:
            n, ef, i = SM2(
                entry.confidence, n, ef, i
            )
            last_review_ts = entry.ts

        next_review_ts = last_review_ts + i * 86400

    access.update_SM2_state(con, problem_id, n, ef, i, last_review_ts, next_review_ts)

def calculate_new_state(n : int, ef : float, i : int, confidence : int, now_ts : int) -> tuple[int, float, int, int]:
    """
    """
    assert 0 <= confidence <= 5, "Confidence must be in range (0-5)"

    n, ef, i = SM2(confidence, n, ef, i)

    next_review_at = now_ts + (i * 86400)

    return n, ef, i, next_review_at

def problem_set_sync(report_func : Callable[[str], None] = lambda _ : None) -> None:
    raw_problem_set = lc_client.fetch_all_problems()

    problems, topics, problem_topics = parse_raw_problem_set(raw_problem_set)

    con = access.get_db_connection()
    try:
        access.populate_db_with_problem_set(con, problems, topics, problem_topics)
        access.set_state(con, 'initial_sync', 'complete')
        con.commit()
        report_func("leetcode.com problem set succesfully saved")
    finally:
        con.close()

def parse_raw_problem_set(problems_raw : list[dict[str, Any]]
    ) -> tuple[
        list[tuple[int, str, str, int]],
        list[tuple[str, str]],
        list[tuple[int, str]]]:
    try:
        problems = [
            (
                int(x['questionFrontendId']),
                str(x['titleSlug']),
                str(x['title']),
                DIFF_TO_INT[x['difficulty']]
            )
            for x in problems_raw
        ]

        topics = list({(str(t['slug']), str(t['name'])) for p in problems_raw for t in p['topicTags']})

        problem_topics = [(int(p['questionFrontendId']), str(t['slug'])) for p in problems_raw for t in p['topicTags']]

        return problems, topics, problem_topics
    except Exception as exc:
        raise Exception("Failed to parse problem set from leetcode.com") from exc

class ProblemNotFoundError(Exception):
    pass

class ProblemAlreadyActiveError(Exception):
    pass

class ProblemAlreadyInactiveError(Exception):
    pass

class EntryNotNoundError(Exception):
    pass

def SM2(grade : int,
        repetition_num : int,
        easiness_factor : float,
        interval : int) -> tuple[int, float, int]:
        """
        Implementation of SuperMemo2 algorithm.

        Args:
            grade (int): A self-evaluation score from 0 to 5 (0 = poor, 5 = excellent).
            repetition_num (int): The no. times the problem has been succesfully reviewed (grade >= 3) in a row.
            easiness_factor (float): Loosely indicates how "easy" the problem is. It determines the rate at which the interval grows.
            interval (int): The inter-repetition interval

        https://en.wikipedia.org/wiki/SuperMemo
        """

        if grade >= 3: # (correct response)
            if repetition_num == 0:
                interval = 1
            elif repetition_num == 1:
                interval = 6
            else:
                interval = round(interval * easiness_factor)
            repetition_num += 1
        else: # (incorrect response)
            repetition_num = 0
            interval = 1

        easiness_factor = easiness_factor + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
        if easiness_factor < 1.3:
            easiness_factor = 1.3

        return repetition_num, easiness_factor, interval

def prepare_cli_database() -> None:
    con = access.get_db_connection()

    try:
        access.bootstap_db(con)
        applied_migrations = access.get_applied_migrations(con)

        migrations = [f for f in os.listdir(MIGRATIONS_DIR) if f.endswith('.sql')]
        migrations.sort()

        to_run = [Path(MIGRATIONS_DIR) / Path(f) for f in migrations if f not in applied_migrations]
        if not to_run:
            return

        for migration in to_run:
            try:
                with open(migration) as f:
                    sql_script = f.read()

                # Attempt to apply the migration
                con.executescript(sql_script)

                # Record it's successful application
                access.record_migration(con, migration.name)

                # Commit now to avoid repeated work
                con.commit()

            except Exception as exc:
                raise FailedMigrationError(f"Migration '{migration.name}' failed for reason: {exc}") from None

    finally:
        con.close()

class FailedMigrationError(Exception):
    pass


