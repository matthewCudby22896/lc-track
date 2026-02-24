import datetime
import random
import uuid

from . import access
from .ds import Problem, Entry, AddEntryEvent

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

        now_ts = int(datetime.datetime.now().timestamp())

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

        # If the above event doesn't raise an exception, commit the transaction
        con.commit()

        # Get updated state of problem
        problem = access.get_problem(con, problem.id)

        return problem, entry
        
    finally:
        con.close()


def calculate_new_state(n : int, ef : float, i : int, confidence : int, now_ts : int) -> tuple[int, float, int, int]:
    """
    """
    assert 0 <= confidence <= 5, "Confidence must be in range (0-5)"

    n, ef, i = SM2(confidence, n, ef, i)

    next_review_at = now_ts + (i * 86400)

    return n, ef, i, next_review_at

class ProblemNotFoundError(Exception):
    pass

class ProblemAlreadyActiveError(Exception):
    pass

class ProblemAlreadyInactiveError(Exception):
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
