import logging
import datetime
import typer
import random
import github
import git
import uuid
import subprocess

from .ds import AddEntryEvent, BaseEvent, Entry, Problem, RmEntryEvent

from . import access
from .utility import initial_sync, date_from_ts, SM2, calculate_new_state
from .constants import BACKUP_REPO_DIR, BACKUP_EVENT_HISTORY, LOCAL_EVENT_HISTORY, TMP_EVENT_HISTORY, YELLOW, GREEN, RED, PURPLE, CYAN, RESET, BOLD_WHITE
from . import backup
from typing import Annotated, List


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
app = typer.Typer(add_completion=False)

colours = {
    "Easy": GREEN,
    "Medium": YELLOW,
    "Hard": RED
}

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
def study():
    """Select a random problem from the set of active problems that are due for review."""
    with access.get_db_connection() as con:
        problems = access.get_for_review_problems(con)

    if not problems:
        typer.echo("No problems due for review.")
        return

    chosen = random.choice(problems)
    
    colour_code = colours.get(chosen.difficulty_txt)

    if not colour_code:
        typer.echo(f"An unexpected error has occured: The chosen question's difficulty text was not recognised (problem_id={chosen.problem_id})")
        raise typer.Exit(1)

    typer.echo(f"To study: LC{chosen.id}. {chosen.title} {colour_code}[{chosen.difficulty_txt}]{RESET}\n")

@app.command(name="ls-active")
def ls_active():
    """ List all problems currently in the active study set. """
    with access.get_db_connection() as con:
        active_problems = access.get_active_problems(con)

    if not active_problems:
        typer.echo("Your active study set is empty. Use 'lc-track activate <id>' to add some!")
        return

    header = f"{BOLD_WHITE}Active Study Set: ({len(active_problems)} problems){RESET}\n" 

    lines = [header] + [
        f"LC{p.id:<4}. {p.title:<50} {colours[p.difficulty_txt]}{p.difficulty_txt}{RESET}\n"
        for p in active_problems
    ]

    text = "".join(lines)
    
    typer.echo(text)

@app.command(name="ls-review")
def ls_for_review():
    """ List all problems, within the active set, currently due for review. """
    with access.get_db_connection() as con:
        due_problems = access.get_for_review_problems(con)

    if not due_problems:
        typer.echo("No problems due for review. You're all caught up!")
        return
    
    header = f"{BOLD_WHITE}Due For Review: ({len(due_problems)} problems){RESET}\n" 

    lines = [header] + [
        f"LC{p.id:<4}. {p.title:<50} {colours[p.difficulty_txt]}{p.difficulty_txt}{RESET}\n"
        for p in due_problems
    ]

    output = "".join(lines)
    
    typer.echo(output)

@app.command(name="activate")
def activate(id: int) -> None:
    """ Add a problem to the active study set. 
    Usage: lc-track activate <problem id>
    """
    with access.get_db_connection() as con:
        problem = access.get_problem(con, id)
    
        if not problem:
            typer.echo(f"No problem found with id: {id}")
            raise typer.Exit(1)

        problem_txt = f"LC{id}. {problem.title} [{colours[problem.difficulty_txt]}{problem.difficulty_txt}{RESET}]"

        if problem.active:
            typer.echo(f"{problem_txt} is already in the active study set.")
            raise typer.Exit(1)

        access.set_active(con, id, True)

    typer.echo(f"{BOLD_WHITE}Added to active study set:{RESET} {problem_txt}")

@app.command(name="deactivate")
def deactivate(id: int) -> None:
    """ Remove a problem from the active study set. 
    Usage: lc-track deactivate <problem id>
    """
    with access.get_db_connection() as con:
        problem = access.get_problem(con, id)
        
        if not problem:
            typer.echo(f"No problem found with id: {id}")
            raise typer.Exit(1)

        problem_txt = f"LC{id}. {problem.title} [{colours[problem.difficulty_txt]}{problem.difficulty_txt}{RESET}]"

        if not problem.active:
            typer.echo(f"{problem_txt} is not in the active study set.")
            raise typer.Exit(1)

        access.set_active(con, id, False)

    typer.echo(f"{BOLD_WHITE}Removed from active study set:{RESET} {problem_txt}")

@app.command(name="details")
def details(id: int) -> None:
    """ Show the details of a LC problem. 
    Usage: lc-track details <problem id>
    """

    with access.get_db_connection() as con:
        problem = access.get_problem(con, id)
        if problem:
            topics = access.get_problem_topics(con, id)
    
    if not problem: 
        typer.echo(f"No problem found with id: {id}")
        raise typer.Exit(1)

    assert(isinstance(problem, Problem))

    now = datetime.datetime.now()
    # Header
    problem_header = f"{BOLD_WHITE}LC{id}. {problem.title}{RESET} [{colours[problem.difficulty_txt]}{problem.difficulty_txt}{RESET}]\n"

    # Last review text
    if problem.last_review_at is not None:
        last_dt = datetime.datetime.fromtimestamp(problem.last_review_at)
        days_past = (now - last_dt).days
        last_review_txt = f"{date_from_ts(problem.last_review_at)} ({days_past} days ago)"
    else:
        last_review_txt = "Never"

    # Next review text
    if not problem.active:
        next_review_txt = "N/A (not in study set)"
    elif problem.next_review_at:
        next_dt = datetime.datetime.fromtimestamp(problem.next_review_at)
        next_date_txt = date_from_ts(problem.next_review_at)

        if now >= next_dt:
            next_review_txt = f"{next_date_txt} (due for review)"
        else:
            diff = next_dt - now
            days = diff.days
            hours = diff.seconds // 3600
            next_review_txt = f"{next_date_txt} (due in {days} days, {hours} hours)"
    else:
        next_review_txt = "Not yet studied (due for review)"

    output = (
        f"{problem_header}"
        f"Topics: {', '.join(topics)}"
        f"Last Review: {last_review_txt}\n"
        f"Next Review: {next_review_txt}\n"
        f"Interval: {problem.i}\n"
        f"Repitition: {problem.n}\n"
        f"Easiness Factor: {problem.ef:.2f}\n"
    )

    typer.echo(output)

@app.command(name="add-entry")
def add_entry(
    id: int,
    confidence: Annotated[int, typer.Argument(min=0, max=5, help="Confidence rating (0-5)")]
) -> None:
    """ Log a completion and update the SM-2 state.
    Usage: lc-track add-entry <problem id> <confidence [0-5]>
    """
    # Get current time
    now_ts = int(datetime.datetime.now().timestamp())

    # Ensure the problem exists
    with access.get_db_connection() as con:
        problem = access.get_problem(con, id) 
    if not problem:
        typer.echo(f"No problem found with id: {id}")
        raise typer.Exit(1)
    
    assert isinstance(problem, Problem)

    # Calculate the new state of the problem, based of the provided confidence rating (0-5)
    n, ef, i, next_rev_ts = calculate_new_state(problem.n, problem.ef, problem.i, confidence, now_ts)
    entry_uuid = str(uuid.uuid4())

    # Update program state in single atomic transaction
    try: 
        con = access.get_db_connection()
        with con:
            # Insert entry (ADD_ENTRY event logged as side effect)
            access.add_entry(
                con,
                Entry(entry_uuid, id, confidence, now_ts)
            )
            # Update the SM2 state of the problem
            access.update_SM2_state(
                con,
                problem.id,
                n,
                ef,
                i,
                now_ts,
                next_rev_ts
            ) 

            # Write event to event history, if this fails the above two changes will be rolled back
            access.append_event(
                AddEntryEvent(str(uuid.uuid4()), now_ts, entry_uuid, problem.id, confidence)
            )

    except Exception as exc:
        typer.echo(f"Failed to log entry: {exc}")
        raise typer.Exit(1)

    finally:
        if con:
            con.close()

    output = (
        f"{BOLD_WHITE}Entry saved: {RESET}{YELLOW}{entry_uuid}{RESET}\n"
        f"LC{problem.id}. {problem.title} [{colours[problem.difficulty_txt]}{problem.difficulty_txt}{RESET}]\n"
        f"Confidence: {confidence}\n"
        f"Streak: {n}\n"
        f"Next Review: {date_from_ts(next_rev_ts)}\n"
    )

    typer.echo(output)


@app.command(name="rm-entry")
def rm_entry(entry_uuid : str) -> None:
    """ Remove an entry and update the SM2 state.
    Usage: lc-track rm-entry <entry uuid>
    """
    now = int(datetime.datetime.now().timestamp())

    # 1. Check than an entry with the uuid exists
    try: 
        con = access.get_db_connection()
        entry = access.get_entry(con, entry_uuid)
    except Exception as exc:
        typer.echo(f"Failed to check for entry existence: {exc}")
        raise typer.Exit(1)

    if not entry:
        logging.info(f"No entry found with uuid: {entry_uuid}")
        raise typer.Exit(1)

    problem_id = entry.problem_id
    
    # 2. Update program state in a single atomic transaction
    try:
        with con:
            access.rm_entry(con, entry_uuid)

            # Get all of the entries with the problem_id    
            entries : List[Entry] = access.get_entries_by_problem_id(con, problem_id)

            # TODO: Move to seperate utility method
            n, ef, i = 0, 2.5, 0 
            if not entries:
                last_review_ts, next_review_ts = 0, 0
            else:
                entries.sort(key = lambda x : x.ts)
                last_review_ts = 0
                for E in entries:
                    n, ef, i = SM2(E.confidence, n, ef, i)
                    last_review_ts = E.ts
                next_review_ts = last_review_ts + int(round(i * 86400))

            access.update_SM2_state(con, problem_id, n, ef, i, last_review_ts, next_review_ts)

            # If the above succeeds without error, append the RM_ENTRY to event log
            access.append_event(
                RmEntryEvent(str(uuid.uuid4()), now, target_entry_uuid=entry_uuid)
            ) # If throws exception, then db rolled back

    except Exception as exc:
        typer.echo(f"Failed to remove entry with uuid={entry_uuid}: {exc}")
        raise typer.Exit(1)

    typer.echo(f"Entry {YELLOW}{entry_uuid}{RESET} removed. LC {problem_id} state recalculated.")

@app.command(name="log")
def log():
    """Show entry logs in a searchable pager."""
    with access.get_db_connection() as con:
        entries = access.get_all_entries(con)

    entries.sort(key = lambda x : x.ts, reverse=True)
    output_lines = []
    
    for E in entries:
        date_str = date_from_ts(E.ts)
        w = 12 
        entry_block = (
            f"{YELLOW}entry {E.uuid}{RESET}\n"
            f"{'Problem ID:':<{w}} {E.problem_id}\n"
            f"{'Confidence:':<{w}} {E.confidence}/5\n"
            f"{'Date:':<{w}} {date_str}\n"
        )
        output_lines.append(entry_block)

    # Join with a newline to separate blocks
    full_text = "\n".join(output_lines)

    try:
        process = subprocess.Popen(['less', '-R'], stdin=subprocess.PIPE, text=True)
        process.communicate(input=full_text)
    except FileNotFoundError:
        print(full_text)

@app.command(name="set-pat")
def set_pat(pat: str = typer.Argument(..., help="Your GitHub Personal Access Token")):
    """
    Update / set your GitHub Personal Access Token in the local database.
    Usage: lc-track set-pat <PAT>
    """
    try:
        with access.get_db_connection() as con:
            access.set_state(con, 'PAT', pat)

    except Exception as exc:
        typer.echo("An unexpected exception has occurred: {exc}")
        raise typer.Exit(1)
    
    typer.echo("Success: GitHub PAT has been saved.")

@app.command(name="setup-backup")
def setup_backup():
    """
    Setup access to a github repository to use as a remote backup of lc-track's event history.
    """
    typer.echo(
        """
        [ LC-TRACK SYNC SETUP ]

        Prerequisites:
        1. A GitHub repository (e.g., 'lc-track-backup')
        2. A Fine-Grained PAT with 'Contents: Read & Write' permissions
        """
    )

    # 1. Inputs
    repo_name = typer.prompt("Backup repository name")
    pat = typer.prompt("GitHub Personal Access Token", hide_input=True)

    g = github.Github(pat)

    # 3. Connection & Authentication
    try: 
        user = g.get_user()
        username = user.login
        typer.echo(f"Connected: Authenticated as {username}")
    except github.BadCredentialsException:
        typer.echo("Error: Invalid PAT. Please verify your token and try again.") 
        with access.get_db_connection() as con:
            access.set_state(con, 'SYNC_SETUP', 'FAILURE')
        raise typer.Exit(1)

    # 4. Repository Verification
    try:
        repo = user.get_repo(repo_name)
        typer.echo(f"Connected: Found {repo_name} repository")
    except github.UnknownObjectException:
        typer.echo(f"Error: Repository '{repo_name}' not found. Check name and PAT scopes.")
        with access.get_db_connection() as con:
            access.set_state(con, 'SYNC_SETUP', 'FAILURE')
        raise typer.Exit(1) 
    
    # 5. Permission Verification
    permissions = repo.permissions
    if not (permissions.push and permissions.pull):
        typer.echo("Error: PAT has insufficient permissions (Read/Write required)")
        with access.get_db_connection() as con:
            access.set_state(con, 'SYNC_SETUP', 'FAILURE')
        raise typer.Exit(1)
    
    typer.echo("Connected: Read and Write access confirmed")

    # 6. Finalize
    with access.get_db_connection() as con:
        access.set_state(con, 'PAT', pat)
        access.set_state(con, 'BACKUP_REPO_NAME', repo_name)
        access.set_state(con, 'USERNAME', username)
        access.set_state(con, 'SYNC_SETUP', 'SUCCESS')
    
    typer.echo("Success: Sync configuration saved")

@app.command(name="sync")
def sync():
    """
    Synchronises the local event history with the remote backup repository.

    Performs a bidirectional sync sync:
    1. Fetches and pulls the latest history from the remote GitHub repository
    2. Merges local and remote event logs to create a unified history.
    3. Push the combined history back to the remote repository
    4. Replays the unified event log to rebuil the local SQLite database.
    """
    
    # 1. Configuration Check
    with access.get_db_connection() as con:
        if access.get_state(con, 'SYNC_SETUP') != 'SUCCESS':
            typer.echo("Error: Sync not configured. Run `lc-track setup-backup` first.")
            raise typer.Exit(1)

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
            typer.echo(f"Failed to initialise local repository from remote:\n\t{exc}")
            raise typer.Exit(1)

        # 3. Handle Empty Remote (First-time use)
        if not repo.refs:
            try:
                typer.echo("Setup: Initialising new remote repository with README.md...")
                readme_file = BACKUP_REPO_DIR / "README.md"
                with open(readme_file, 'w', encoding='utf-8') as f:
                    f.write("# lc-track remote backup\n Event history backup for LeetCode tracking.") 

                repo.index.add(['README.md'])
                repo.index.commit("Initial setup")
                repo.remotes.origin.push('main:main')

            except Exception as exc:
                typer.echo(f"Failed to handle initialisation of empty repository:\n\t{exc}")
                raise typer.Exit(1)

    # 4. The Sync Process
    try:
        # Step 1: Pull
        typer.echo("Sync [1/4]: Fetching latest remote history...")
        repo.remotes.origin.pull()

        # Step 2: Merge logic
        typer.echo("Sync [2/4]: Merging local and backup event logs...")
        event_history : List[BaseEvent] = backup.merge_event_logs(BACKUP_EVENT_HISTORY, LOCAL_EVENT_HISTORY)

        # Atomic writes to both destinations
        for target_path in [BACKUP_EVENT_HISTORY, LOCAL_EVENT_HISTORY]:
            backup.write_event_log(TMP_EVENT_HISTORY, event_history)
            TMP_EVENT_HISTORY.replace(target_path)

        # Step 3: Push back to remote
        typer.echo("Sync [3/4]: Uploading synchronised history to GitHub...")
        repo.index.add([BACKUP_EVENT_HISTORY.name]) # Use .name if it's a Path object
        if repo.is_dirty():
            repo.index.commit("Sync: Combined local and remote histories")
            repo.remotes.origin.push()
        else:
            typer.echo("Status: Remote already up to date.")

        # Step 4: Database Rebuild
        typer.echo("Sync [4/4]: Rebuilding local database state from event history...")
        backup.update_state_from_local_event_history()

        typer.echo("Done: Sync successful. Local state and remote state are now up to date.")

    except Exception as exc:
        typer.echo(f"Error: An unexpected error occurred during sync:\n\t{exc}")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
