import datetime
import logging
from typing import Tuple

from .lc_client import fetch_all_problems
from . import access

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

def SM2(q : int,
        n : int, 
        EF : float,
        I : int) -> Tuple[int, float, int]:

        if q >= 3: # (correct response)
            if n == 0:
                I = 1
            elif n == 1:
                I = 6
            else:
                I = round(I * EF)
            n += 1
        else: # (incorrect response)
            n = 0
            I = 1

        EF = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        if EF < 1.3:
            EF = 1.3
        
        return n, EF, I
        
def calculate_new_state(n : int, ef : float, i : int, confidence : int, now_ts : int) -> Tuple[int, float, int, int]:
    """ 
    """
    assert 0 <= confidence <= 5, "Confidence must be in range (0-5)"

    n, ef, i = SM2(confidence, n, ef, i)

    next_review_at = now_ts + (i * 86400)

    return n, ef, i, next_review_at