import time
from typing import Any

import requests
from rich.progress import track

GRAPHQL_ENDPOINT = "https://leetcode.com/graphql"
LIMIT = 100

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0...",
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com"
})

def fetch_all_problems() -> list[dict[str, Any]]:

    query = """
    query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
      problemsetQuestionList: questionList(
        categorySlug: $categorySlug
        limit: $limit
        skip: $skip
        filters: $filters
      ) {
        totalNum
        questions: data {
          questionFrontendId
          title
          titleSlug
          difficulty
          topicTags {
            name
            slug
          }
        }
      }
    }
    """

    problem_set : list[dict[str, Any]]= []
    payload : dict[str, Any]= {
        "query" : query,
        "variables" : {"categorySlug": "", "skip": 0, "limit": LIMIT, "filters": {}}
    }

    total = None

    try:
        res = session.post(GRAPHQL_ENDPOINT, json=payload)
        res.raise_for_status()
        data = res.json()

        total = data['data']['problemsetQuestionList']['totalNum']
        problem_set = extract_problem_batch(data)

        for skip in track(range(LIMIT, total, LIMIT), description="Fetch problem set"):
            payload['variables']['skip'] = skip

            res = session.post(GRAPHQL_ENDPOINT, json=payload)
            res.raise_for_status()

            batch_data = res.json()
            problem_set.extend(extract_problem_batch(batch_data))

            time.sleep(0.1)

    except requests.exceptions.RequestException as e:
        raise Exception(f"Network error connecting to LeetCode: {e}") from None
    except KeyError:
        raise Exception("LeetCode API response format has changed.") from None

    return problem_set

def extract_problem_batch(data : dict[str, Any]) -> list[dict[str, Any]]:
  return data['data']['problemsetQuestionList']['questions']
