import datetime
from typing import Annotated

import github
import typer

from . import access, backup, service
from .constants import (
    BOLD_WHITE,
    DIFF_COLOUR,
    GREEN,
    RED,
    RESET,
    YELLOW,
)

app = typer.Typer(add_completion=False)

def fmt_date(ts):
    return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M') if ts else "Never"

# TODO: Switch to a better system of tracking database migrations
@app.callback()
def main():
    """
    LeetCode-Track CLII
    """
    if not access.db_exists():
        service.init_db()
        echo_success("Local database initialised")

    if service.get_state('initial_sync') != 'complete':
        try:
            service.problem_set_sync()
        except Exception as exc:
            abort(f"An unexpected error occurred whilst syncing problem set: {exc}")

        echo_success(f"{BOLD_WHITE}lc-track setup complete{RESET}")

@app.command(name="study")
def study() -> None:
    """Select a random problem from the set of active problems that are due for review."""
    try:
        problem = service.get_problem_to_study()
    except Exception as exc:
        abort(f"An unexpected error occurred: {exc}")

    if not problem:
        typer.echo("No problems due for review.")
        raise typer.Exit(0) from None

    colour_code = DIFF_COLOUR.get(problem.difficulty_txt)

    typer.echo(f"To study: LC{problem.id}. {problem.title} {colour_code}[{problem.difficulty_txt}]{RESET}\n")

@app.command(name="ls-active")
def ls_active() -> None:
    """ List all problems currently in the active study set. """
    try:
        active_problems = service.get_active_problems()
    except Exception as exc:
        abort(f"An unexpected error occurred: {exc}")

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
    try:
        due_problems = service.get_for_review_problems()
    except Exception as exc:
        abort(f"An unexpected error occurred: {exc}")

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
        abort(f"No problem found with id : '{id}'")

    except service.ProblemAlreadyActiveError:
        abort("Problem already active")

    except Exception as exc:
        abort(f"An unexpected error occurred: {exc}")

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
        abort(f"No problem found with id : '{id}'")

    except service.ProblemAlreadyInactiveError:
        abort("Problem is not currently active")

    except Exception as exc:
        abort(f"An unexpected error occurred: {exc}")

@app.command(name="details")
def details(id: int) -> None:
    """ Show the details of a LC problem.
    Usage: lc-track details <problem-id>
    """
    try:
        problem, topics = service.get_problem_and_topics(id)

    except service.ProblemNotFoundError:
        abort(f"No problem found with id : '{id}'")

    except Exception as exc:
        abort(f"An unexpected error occurred: {exc}")

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
        abort(f"No problem found with id : '{id}'.")
    except Exception as exc:
        abort(f"An unexpected error occurred: {exc}")

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
        abort(f"An unexpected error occurred: {exc}")

    typer.echo(f"Entry {YELLOW}{entry_uuid}{RESET} removed. LC {problem_id} state recalculated.\n")

@app.command(name="log")
def log():
    """Show entry logs in a searchable pager."""
    try:
        text = service.build_entry_log()
    except Exception as exc:
        abort(f"An unexpected error occurred: {exc}")

    typer.echo_via_pager(text)

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
        service.finalise_backup_setup(pat, repo_name, user.login)
    except Exception as exc:
        abort(f"An unexpected error occurred: {exc}")

    echo_success("Backup / sync configuration saved")

# TODO: Refactor in progress
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

    pat : str | None = access.get_pat()
    if not pat:
        abort("Github PAT not set. Refer to `lc-track setup-backup`")

    repo_name : str | None = service.get_repo_name()
    if not repo_name:
        abort("Backup repo name unknown. Refer to `lc-track setup-backup`")

    user : str | None = service.get_user()
    if not user:
        abort("Github user unknown. Refer to `lc-track setup-backup`")

    auth_url = f"https://{pat}@github.com/{user}/{repo_name}.git"

    # Get repo
    try:
        repo = backup.get_repo(auth_url, report_func=echo_success)
        if not repo.refs:
            backup.populate_empty_repo(repo, report_func=echo_success)

    except Exception as exc:
        abort(f"An unexpected error occurred: {exc}")

    # Sync
    try:
        backup.event_log_sync(repo, report_func=echo_success)
    except Exception as exc:
        abort(f"An unexpected error occurred: {exc}")

if __name__ == "__main__":
    app()
