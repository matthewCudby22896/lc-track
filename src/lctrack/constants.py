from enum import StrEnum
from pathlib import Path

from platformdirs import PlatformDirs

dirs = PlatformDirs('lc-track','lc-track')

# Data Directory:
DATA_DIR = Path(dirs.user_data_dir)
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_LOC = DATA_DIR / "database.db"

BACKUP_REPO_DIR = DATA_DIR / "backup"
BACKUP_REPO_DIR.mkdir(parents=True, exist_ok=True)

BACKUP_EVENT_LOG_LOC = BACKUP_REPO_DIR / "event_log_backup.jsonl"
LOCAL_EVENT_LOG_LOC = DATA_DIR / "event_log_local.jsonl"
TMP_EVENT_LOG_LOC = DATA_DIR / "tmp_event_log.jsonl"

# Source code
BASE_PATH = Path(__file__).resolve().parent.parent # src
MIGRATIONS_DIR = BASE_PATH / "lctrack" / "migrations"
PROBLEM_SET_F_LOC = BASE_PATH / "lctrack" / "problem_sets" / "problem_sets.json"

# Constants
YELLOW = "\033[33m" # MEDIUM
GREEN = "\033[32m" # EASY
RED = "\033[31m" # HARD
BOLD_WHITE = "\033[1;37m"
RESET = "\033[0m"

DIFF_COLOUR = {
    "Easy": GREEN,
    "Medium": YELLOW,
    "Hard": RED
}

class StudyMode(StrEnum):
    RANDOM = "random"
    SMART = "smart"

class StudySets(StrEnum):
    BLIND75 = "blind75"
    NEETCODE150 = "neetcode150"

DEFAULT_STUDY_MODE = StudyMode.SMART

type ProblemSlug = str
type ProblemTitle = str
type FrontendID = int
type TopicSlug = str
type TopicText = str

