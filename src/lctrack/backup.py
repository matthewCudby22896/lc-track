
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import git
import github
from github.AuthenticatedUser import AuthenticatedUser
from github.NamedUser import NamedUser
from github.Repository import Repository
from lctrack.service import SM2

from . import access
from .constants import (
    BACKUP_EVENT_LOG_LOC,
    BACKUP_REPO_DIR,
    LOCAL_EVENT_LOG_LOC,
    TMP_EVENT_LOG_LOC,
)
from .ds import AddEntryEvent, BaseEvent, RmEntryEvent


def merge_event_logs(hist1 : Path, hist2 : Path) -> list[BaseEvent]:
    # Load both event histories into memory
    events_local : list[BaseEvent] = load_event_log(hist1)
    events_backup : list[BaseEvent] = load_event_log(hist2)

    # Merge the two into a single list of unique events, sorted by ts
    combined_events = list({event.uuid: event for event in events_backup + events_local}.values())
    combined_events.sort(key=lambda x : x.ts)

    return combined_events

def load_event_log(path : Path) -> list[BaseEvent]:
    """ Load an event log from a JSON lines (.jsonl) file.

    Each non-empty line is parsed as JSON and converted into a subclass of BaseEvent.
    """
    if not path.exists():
        return []

    events : list[BaseEvent] = []
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            stripped_line : str = line.strip()
            if not line:
                continue
            try:
                events.append(jsonl_to_event(json.loads(stripped_line)))

            except json.JSONDecodeError as exc:
                raise Exception(f"Failed to parse ln {ln} of {f}: {exc}") from None

    return events

def jsonl_to_event(_jsonl : dict[str, Any]) -> BaseEvent:
    """ Convert a raw JSONL event dictionary into an instance of a concrete subclass of BaseEvent.

    The event type is determined by the value of the 'EVENT_TYPE' key.
    """
    if _jsonl.get('EVENT_TYPE', None) is None:
        raise ValueError(f"event in _jsonl form is lacking required 'EVENT_TYPE' key: {_jsonl}")

    if _jsonl['EVENT_TYPE'] == "ADD_ENTRY":
        return AddEntryEvent.from_dict(_jsonl)
    elif _jsonl['EVENT_TYPE'] == "RM_ENTRY":
        return RmEntryEvent.from_dict(_jsonl)
    else:
        raise ValueError(f"event in _jsonl form has unexpected event type: 'EVENT_TYPE : {_jsonl['EVENT_TYPE']}'")

def write_event_log(loc : Path, event_log : list[BaseEvent]) -> None:
    """ Writes an event log consisting of a list of events to the specified location.
    """
    with open(loc, 'w', encoding="utf-8") as f:
        for event in event_log:
            line = json.dumps(event.to_dict())
            f.write(line + '\n')

def update_state_from_local_event_log() -> None:
    """
    Steps:
    1. Clear the entries database table
    2. Run through the events stored under LOCAL_EVENT_HISTORY updating the entries database table
    3. Wipe the problem state for all problems
    4. Run through every entry within entries in chronological order to derive the correct state of each problem
    """

    with access.get_db_connection() as con:
        access.clear_entries_table(con)

        # 1. Load all events from the local version of the event log
        events = load_event_log(LOCAL_EVENT_LOG_LOC)

        # 2. Process all events in chronological order
        for event in events:
            access.process_event(con, event)

        # 3. Update the state of all problems based of the entries under the entries table
        entries = access.get_all_entries(con)

        sm2_states : dict[int, tuple[int, float, int, int, int]] = {} # problem_id -> SM2 state (n, EF, I, last_review_ts, next_review_ts)

        for E in entries:
            if E.problem_id not in sm2_states:
                n, EF, I = (0, 2.5, 0)
            n, EF, I = SM2(E.confidence, n, EF, I)
            last_review_at = E.ts
            next_review_at = last_review_at + int(I * 86400)

            sm2_states[E.problem_id] = (n, EF, I, last_review_at, next_review_at)

        new_states = [
            (v[0], v[1], v[2], v[3], v[4], k)
            for k, v in sm2_states.items()
        ]

        access.bulk_update_problem_state(con, new_states)

# BACKUP/SYNC SETUP

def auth_github_user(pat : str) -> tuple[github.Github, AuthenticatedUser]:
    g = github.Github(
        auth=github.Auth.Token(pat)
    )

    user : NamedUser | AuthenticatedUser = g.get_user() # Lazy auth

    # Forces a request to fetch the login
    _ = user.login # May raise a GithubException for error status codes

    assert isinstance(user, AuthenticatedUser)

    return g, user

def get_github_repo(user : AuthenticatedUser, repo_name : str) -> Repository:
    return user.get_repo(repo_name)

def verify_repo_permissions(repo: Repository):
    p = repo.permissions

    if not p.push and not p.pull:
        raise MissingPermissionsError("push & pull")

    if not p.push:
        raise MissingPermissionsError("push")

    if not p.pull:
        raise MissingPermissionsError("pull")

def finalise_backup_setup(pat : str, repo_name: str, user : str):
    con = access.get_db_connection()

    try:
        access.set_pat(pat)
        access.set_state(con, 'BACKUP_REPO_NAME', repo_name)
        access.set_state(con, 'USER', user)
        con.commit()
    finally:
        con.close()

# SYNC LOGIC

def get_repo(auth_url,
             report_func: Callable[[str], None] = lambda _: None) -> git.Repo:
    if not check_repo(BACKUP_REPO_DIR):
        repo = git.Repo.clone_from(auth_url, BACKUP_REPO_DIR)
        report_func(f"Cloned backup repo to '{BACKUP_REPO_DIR.relative_to(Path.home())}'")
    else:
        repo = git.Repo(BACKUP_REPO_DIR)
        repo.remotes.origin.set_url(auth_url)
        report_func(f"Backup repo found '{BACKUP_REPO_DIR}'")

    return repo

def check_repo(path : Path) -> bool:
    try:
        git.Repo(path)
        # If this succeeds, this is a valid repo
        return True
    except git.InvalidGitRepositoryError:
        # The folder exists, but it's not a git repo
        return False
    except git.NoSuchPathError:
        # The folder doesn't even exist
        return False

def populate_empty_repo(repo : git.Repo, report_func: Callable[[str], None] = lambda _ : None) -> None:
    readme_file = BACKUP_REPO_DIR / "README.md"
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write("# lc-track remote backup\n Event log backup for `lc-track`")
    repo.index.add(['README.md'])
    repo.index.commit("Initial commit")
    repo.remotes.origin.push('main:main')

def event_log_sync(repo : git.Repo, report_func: Callable[[str], None] = lambda _ : None) -> None:
    repo.remotes.origin.pull()
    report_func("Latest remote event log pulled")

    event_log : list[BaseEvent] = merge_event_logs(BACKUP_EVENT_LOG_LOC, LOCAL_EVENT_LOG_LOC)
    report_func("Event logs merged")

    # Atomic writes
    for target_path in [BACKUP_EVENT_LOG_LOC, LOCAL_EVENT_LOG_LOC]:
        write_event_log(TMP_EVENT_LOG_LOC, event_log)
        TMP_EVENT_LOG_LOC.replace(target_path)

    update_state_from_local_event_log()
    report_func("Local state updated")

    repo.index.add([BACKUP_EVENT_LOG_LOC.name])

    if repo.index.diff("HEAD"):
        repo.index.commit("Sync: merged event logs")
        repo.remotes.origin.push()
        report_func("Merged event log pushed to remote")
    else:
        report_func("Remote is already up-to-date")

# ERRORS

class MissingPermissionsError(Exception):
    pass

class FailedAuthError(Exception):
    pass
