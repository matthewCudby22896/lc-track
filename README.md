# lc-track

A command-line interface for tracking LeetCode study progress, utilising the [SuperMemo-2](https://en.wikipedia.org/wiki/SuperMemo) (SM-2) spaced repetition algorithm to optimise review schedules. This is a study tool for personal use.

Built with:
- python3
- SQLite
- and the [typer](https://typer.tiangolo.com/) library.

### Commands

<img width="940" height="567" alt="lc-track CLI help menu" src="https://github.com/user-attachments/assets/e6e6b955-2c7c-40be-9ee3-e74fc9ccad50" />

### Confidence Levels

| Level | Name | Description |
| :--- | :--- | :--- |
| **0** | **Complete Failure** | No recall; unable to formulate a solution. |
| **1** | **Recognised** | Failed the problem, but the solution was understood upon review. |
| **2** | **Near Miss** | Failed to pass, but was very close to a functional implementation. |
| **3** | **Strenuous** | Correct solution, but required significant mental effort or time. |
| **4** | **Proficient** | Correct solution; implemented with minor hesitation or thought. |
| **5** | **Perfect** | Instant, effortless recall and flawless implementation. |

### Sync & Backup

Users can back up their study logs using the `lc-track setup-backup` and `lc-track sync` commands. 

```text
user@fedora:~$ lc-track setup-backup
        [ LC-TRACK SYNC SETUP ]

        Prerequisites:
        1. A GitHub repository (e.g., 'lc-track-backup')
        2. A Fine-Grained PAT with 'Contents: Read & Write' permissions
        for the given repository
        
Repository Name: lc-track-backup
GitHub Personal Access Token: 
[success] Authenticated as user12345
[success] lc-track-backup repo found
[success] Read & write permissions confirmed
[success] Backup / sync configuration saved
```

```text
user@fedora:~$ lc-track setup-backup
[success] Backup repo found '~/.local/share/lc-track/backup'
[success] Latest remote event log pulled
[success] Event logs merged
[success] Local state updated
[success] Merged event log pushed to remote
```

### Development Commands

```shell
# Execute the CLI directly via Python
python3 -m src.lc.track

# Install the project in editable (development) mode
pip3 install -e .

# Run static type checking
mypy

# Run the linter
ruff check . --fix
