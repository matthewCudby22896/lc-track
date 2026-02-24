import random

from . import access
from .ds import Problem


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

class ProblemNotFoundError(Exception):
    pass

class ProblemAlreadyActiveError(Exception):
    pass

class ProblemAlreadyInactiveError(Exception):
    pass

