import datetime
import logging
import subprocess
from typing import Annotated

import git
import github
import typer

from . import access, backup, service
from .constants import (
    BACKUP_EVENT_LOG,
    BACKUP_REPO_DIR,
    BOLD_WHITE,
    DIFF_COLOUR,
    GREEN,
    LOCAL_EVENT_LOG,
    RED,
    RESET,
    TMP_EVENT_LOG,
    YELLOW,
)
from .ds import BaseEvent
from .utility import initial_sync

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
app = typer.Typer(add_completion=False)


def fmt_date(ts):
    return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M') if ts else "Never"

@app.callback()
def main():
    """
    LeetCode-Track CLI
    """
    if not access.db_exists():
        typer.echo("Initialising lc-track local database...")
        access.init_db()

    if access.db_exists():
        with access.get_db_connection() as con:
            if access.get_state(con, "initial_sync") != "complete":
                initial_sync()
                typer.echo(f"{BOLD_WHITE}lc-track setup complete.{RESET}\n")

@app.command(name="study")
def study() -> None:
    """Select a random problem from the set of active problems that are due for review."""

    problem = service.get_problem_to_study()

    if not problem:
        typer.echo("No problems due for review.")
        raise typer.Exit(0) from None

    colour_code = DIFF_COLOUR.get(problem.difficulty_txt)

    typer.echo(f"To study: LC{problem.id}. {problem.title} {colour_code}[{problem.difficulty_txt}]{RESET}\n")

@app.command(name="ls-active")
def ls_active() -> None:
    """ List all problems currently in the active study set. """
    active_problems = service.get_active_problems()

    if not active_problems:
        typer.echo("Your active study set is empty. Use 'lc-track activate <id>' to add some!")
        raise typer.Exit(0) from None

    header = f"{BOLD_WHITE}Active Study Set: ({len(active_problems)} problems){RESET}\n"

    problem_rows = (
        f"LC{p.id:<4}. {p.title:<50} {DIFF_COLOUR[p.difficulty_txt]}{p.difficulty_txt}{RESET}\n"
        for p in active_problems
    )

    text = header + "".join(problem_rows)

    typer.echo(text)

@app.command(name="ls-review")
def ls_for_review():
    """ List all problems, within the active set, currently due for review. """
    due_problems = service.get_for_review_problems()

    if not due_problems:
        typer.echo("No problems due for review. You're all caught up!")
        raise typer.Exit(0) from None

    header = f"{BOLD_WHITE}Due For Review: ({len(due_problems)} problems){RESET}\n"

    problem_rows = (
        f"LC{p.id:<4}. {p.title:<50} {DIFF_COLOUR[p.difficulty_txt]}{p.difficulty_txt}{RESET}\n"
        for p in due_problems
    )

    text = header + "".join(problem_rows)

    typer.echo(text)

@app.command(name="activate")
def activate(id: int) -> None:
    """ Add a problem to the active study set.
    Usage: lc-track activate <problem-id>
    """

    try:
        problem = service.activate_problem(id)

        problem_txt = f"LC{id}. {problem.title} [{DIFF_COLOUR[problem.difficulty_txt]}{problem.difficulty_txt}{RESET}]"
        typer.echo(f"{BOLD_WHITE}Added to active study set:{RESET} {problem_txt}\n")

    except service.ProblemNotFoundError:
        typer.echo(f"No problem found with id : '{id}'.")
        raise typer.Exit(1) from None

    except service.ProblemAlreadyActiveError:
        typer.echo("Problem already active.")
        raise typer.Exit(1) from None

    except Exception as exc:
        typer.echo(f"{RED}An unexpected error occurrred:{RESET} {exc}")
        raise typer.Exit(1) from None

@app.command(name="deactivate")
def deactivate(id: int) -> None:
    """ Remove a problem from the active study set.
    Usage: lc-track deactivate <problem-id>
    """

    try:
        problem = service.deactivate_problem(id)

        problem_txt = f"LC{id}. {problem.title} [{DIFF_COLOUR[problem.difficulty_txt]}{problem.difficulty_txt}{RESET}]"
        typer.echo(f"{BOLD_WHITE}Removed from active study set:{RESET} {problem_txt}\n")

    except service.ProblemNotFoundError:
        typer.echo(f"No problem found with id : '{id}'.")
        raise typer.Exit(1) from None

    except service.ProblemAlreadyInactiveError:
        typer.echo("Problem is not currently active.")
        raise typer.Exit(1) from None

    except Exception as exc:
        typer.echo(f"{RED}An unexpected error occurred:{RESET} {exc}")
        raise typer.Exit(1) from None


@app.command(name="details")
def details(id: int) -> None:
    """ Show the details of a LC problem.
    Usage: lc-track details <problem-id>
    """
    try:
        problem, topics = service.get_problem_and_topics(id)

    except service.ProblemNotFoundError:
        typer.echo(f"No problem found with id : '{id}'.")
        raise typer.Exit(1) from None

    except Exception as exc:
        typer.echo(f"{RED}An unexpected error occurred:{RESET} {exc}")
        raise typer.Exit(1) from None

    text = (
        f"{BOLD_WHITE}LC{id}. {problem.title}{RESET} [{DIFF_COLOUR[problem.difficulty_txt]}{problem.difficulty_txt}{RESET}]\n"
        f"Topics: {', '.join(topics)}\n"
        f"\n"
        f"{BOLD_WHITE}Problem State{RESET}\n"
        f"Last Review: {problem.last_review_txt()}\n"
        f"Next Review: {problem.next_review_txt()}\n"
        f"Interval: {problem.i}\n"
        f"Repitition: {problem.n}\n"
        f"Easiness Factor: {problem.ef:.2f}\n"
    )

    typer.echo(text)

@app.command(name="add-entry")
def add_entry(
    id: int,
    confidence: Annotated[int, typer.Argument(min=0, max=5, help="Confidence rating (0-5)")]
) -> None:
    """ Log a completion and update the SM-2 state.
    Usage: lc-track add-entry <problem-id> <confidence [0-5]>
    """
    try:
        problem, entry = service.add_entry(id, confidence)
    except service.ProblemNotFoundError:
        typer.echo(f"No problem found with id : '{id}'.")
        raise typer.Exit(1) from None
    except Exception as exc:
        typer.echo(f"{RED}An unexpected error occurred:{RESET} {exc}")
        raise typer.Exit(1) from None

    text = (
        f"{BOLD_WHITE}Entry saved: {RESET}{YELLOW}{entry.uuid}{RESET}\n"
        f"LC{problem.id}. {problem.title} [{DIFF_COLOUR[problem.difficulty_txt]}{problem.difficulty_txt}{RESET}]\n"
        f"Confidence: {confidence}\n"
        f"Streak: {problem.n}\n"
        f"Next Review: {problem.next_review_txt()}\n"
    )

    typer.echo(text)

@app.command(name="rm-entry")
def rm_entry(entry_uuid : str) -> None:
    """ Remove an entry and update the SM2 state.
    Usage: lc-track rm-entry <entry-uuid>
    """
    try:
        problem_id = service.rm_entry(entry_uuid)
    except service.EntryNotNoundError:
        typer.echo(f"No entry found with uuid : '{entry_uuid}'")
        raise typer.Exit(1) from None
    except Exception as exc:
        typer.echo(f"{RED}An unexpected error occurred:{RESET} {exc}")
        raise typer.Exit(1) from None

    typer.echo(f"Entry {YELLOW}{entry_uuid}{RESET} removed. LC {problem_id} state recalculated.\n")

@app.command(name="log")
def log():
    """Show entry logs in a searchable pager."""

    text = service.build_entry_log()
    try:
        process = subprocess.Popen(['less', '-R'], stdin=subprocess.PIPE, text=True)
        process.communicate(input=text)
    except FileNotFoundError:
        typer.echo(text)
    except Exception as exc:
        typer.echo(f"{RED}An unexpected error occurred:{RESET} {exc}")
        raise typer.Exit(1) from None

# TODO: Possibly make a request to Github to determine the permissions of the token
# Outputting them to the user, and warning them if it's missing required permissions
@app.command(name="set-pat")
def set_pat():
    """
    Update / set your GitHub Personal Access Token in the local database.
    """
    pat = typer.prompt("GitHub Personal Access Token", hide_input=True)
    try:
        service.set_pat(pat)
    except Exception as exc:
        typer.echo(f"{RED}An unexpected error occurred:{RESET} {exc}")
        raise typer.Exit(1) from None

    typer.echo(f"{BOLD_WHITE}Success: GitHub PAT has been saved. {RESET}")

def abort(msg: str) -> None:
    typer.echo(f"{RED}[error]{RESET} {msg}")
    raise typer.Exit(1) from None

def echo_success(msg: str) -> None:
    typer.echo(f"{GREEN}[success]{RESET} {msg}")

@app.command(name="setup-backup")
def setup_backup():
    """
    Setup access to a github repository to use as a remote backup of lc-track's event log.
    """
    typer.echo(
        f"""
        {BOLD_WHITE}[ LC-TRACK SYNC SETUP ]{RESET}

        Prerequisites:
        1. A GitHub repository (e.g., 'lc-track-backup')
        2. A Fine-Grained PAT with 'Contents: Read & Write' permissions
        for the given repository
        """
    )
    repo_name = typer.prompt("Repository Name")
    pat = typer.prompt("GitHub Personal Access Token", hide_input=True)

    # Authenticate
    try:
        _, user = service.auth_user(pat)

    except github.BadCredentialsException:
        abort("Bad credentials")
    except Exception as exc:
        abort(f"An unexpected error occurred: {exc}")

    echo_success(f"Authenticated as {BOLD_WHITE}{user.login}{RESET}")

    # Verify existence of repository for authenticated user
    try:
        repo = service.verify_repository(user, repo_name)
    except github.UnknownObjectException:
        abort(f"Repository '{repo_name}' not found")
    except Exception as exc:
        abort(f"An unexpected error occurred: {exc}")

    echo_success(f"{BOLD_WHITE}{repo_name}{RESET} found")

    # Verify correct permissions (pull & push)
    try:
        service.verify_permissions(repo)
    except service.MissingPermissionsError as exc:
        abort(f"Missing permission '{exc}'")
    except Exception as exc:
        abort(f"An unexpected error occurred: {exc}")

    echo_success("Read & write permissions confirmed")

    # Save the PAT within keyring, and save repo name to db
    try:
        service.finalise_backup_setup(pat, repo_name)
    except Exception as exc:
        abort(f"An unexpected error occurred: {exc}")

    echo_success("Backup / sync configuration saved")

@app.command(name="sync")
def sync() -> None:
    """
    Synchronises the local event log with the remote backup repository.

    Performs a bidirectional sync sync:
    1. Fetches and pulls the latest event log from the remote GitHub repository
    2. Merges local and remote event logs to create a unified log.
    3. Push the combined event log back to the remote repository
    4. Replays the unified event log to rebuil the local SQLite database.
    """

    # 1. Configuration Check
    with access.get_db_connection() as con:
        if access.get_state(con, 'SYNC_SETUP') != 'SUCCESS':
            typer.echo("Error: Sync not configured. Run `lc-track setup-backup` first.\n")
            raise typer.Exit(1) from None

        pat = access.get_state(con, 'PAT')
        repo_name = access.get_state(con, 'BACKUP_REPO_NAME')
        username = access.get_state(con, 'USERNAME')
        auth_url = f"https://{pat}@github.com/{username}/{repo_name}.git"

        # 2. Repository Initialisation
        try:
            if not access.check_repo(BACKUP_REPO_DIR):
                typer.echo(f"Initialisation: Cloning remote backup to {BACKUP_REPO_DIR}...")
                repo = git.Repo.clone_from(auth_url, BACKUP_REPO_DIR)
            else:
                repo = git.Repo(BACKUP_REPO_DIR)
                repo.remotes.origin.set_url(auth_url)
        except Exception as exc:
            typer.echo(f"Failed to initialise local repository from remote:\n\t{exc}\n")
            raise typer.Exit(1) from None

        # 3. Handle Empty Remote (First-time use)
        if not repo.refs:
            try:
                typer.echo("Setup: Initialising new remote repository with README.md...")
                readme_file = BACKUP_REPO_DIR / "README.md"
                with open(readme_file, 'w', encoding='utf-8') as f:
                    f.write("# lc-track remote backup\n Event log backup for LeetCode tracking.")

                repo.index.add(['README.md'])
                repo.index.commit("Initial setup")
                repo.remotes.origin.push('main:main')

            except Exception as exc:
                typer.echo(f"Failed to handle initialisation of empty repository:\n\t{exc}\n")
                raise typer.Exit(1) from None

    # 4. The Sync Process
    try:
        # Step 1: Pull
        typer.echo("Sync [1/4]: Fetching latest remote event log...")
        repo.remotes.origin.pull()

        # Step 2: Merge logic
        typer.echo("Sync [2/4]: Merging local and backup event logs...")
        event_log : list[BaseEvent] = backup.merge_event_logs(BACKUP_EVENT_LOG, LOCAL_EVENT_LOG)

        # Atomic writes to both destinations
        for target_path in [BACKUP_EVENT_LOG, LOCAL_EVENT_LOG]:
            backup.write_event_log(TMP_EVENT_LOG, event_log)
            TMP_EVENT_LOG.replace(target_path)

        # Step 3: Push back to remote
        typer.echo("Sync [3/4]: Uploading synchronised event log to GitHub...")
        repo.index.add([BACKUP_EVENT_LOG.name])
        if repo.is_dirty():
            repo.index.commit("Sync: Combined local and remote histories")
            repo.remotes.origin.push()
        else:
            typer.echo("Status: Remote already up to date.")

        # Step 4: Database Rebuild
        typer.echo("Sync [4/4]: Rebuilding local database state from event log...")
        backup.update_state_from_local_event_log()

        typer.echo("Done: Sync successful. Local state and remote state are now in synchronised state.\n")

    except Exception as exc:
        typer.echo(f"Error: An unexpected error occurred during sync:\n\t{exc}\n")
        raise typer.Exit(1) from None

if __name__ == "__main__":
    app()
