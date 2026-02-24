import datetime
import logging

from . import access
from .lc_client import fetch_all_problems

DIFF_TO_INT = {
    "Hard" : 2,
    "Medium" : 1,
    "Easy" : 0
}

def initial_sync() -> None:
    problems_raw = fetch_all_problems()

    try:
        problems = [
            (x['questionFrontendId'], x['titleSlug'], x['title'], DIFF_TO_INT[x['difficulty']])
            for x in problems_raw
        ]

        topics = {(t['slug'], t['name']) for p in problems_raw for t in p['topicTags']}

        problem_topics = [(p['questionFrontendId'], t['slug']) for p in problems_raw for t in p['topicTags']]

    except Exception as e:
        logging.error(f"Failed to parse problem set fetched from leetcode.com: {e}")
        return

    con = access.get_db_connection()
    try:
        with con:
            cur = con.cursor()

            stmt = "INSERT INTO problems (id, slug, title, difficulty) VALUES (?, ?, ?, ?);"
            cur.executemany(stmt, problems)

            stmt = "INSERT INTO topics (topic_slug, topic_title) VALUES (?, ?);"
            cur.executemany(stmt, topics)

            stmt = "INSERT INTO problem_topic (problem_id, topic_slug) VALUES (?, ?);"
            cur.executemany(stmt, problem_topics)

            access.set_state(con, "initial_sync", "complete")

    except Exception as e:
        logging.error(f"Failed to sync problem set with leetcode.com: {e}")
    finally:
        con.close()

def date_from_ts(unix_ts : int) -> str:
    return datetime.datetime.fromtimestamp(unix_ts).strftime("%Y-%m-%d %H:%M")


def SM2(grade : int,
        repetition_num : int,
        easiness_factor : float,
        interval : int) -> tuple[int, float, int]:
        """
        Implementation of SuperMemo algorithm.

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
def calculate_new_state(n : int, ef : float, i : int, confidence : int, now_ts : int) -> tuple[int, float, int, int]:
    """
    """
    assert 0 <= confidence <= 5, "Confidence must be in range (0-5)"

    n, ef, i = SM2(confidence, n, ef, i)

    next_review_at = now_ts + (i * 86400)

    return n, ef, i, next_review_at
