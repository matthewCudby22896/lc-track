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
