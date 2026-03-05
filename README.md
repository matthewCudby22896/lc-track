# lc-track CLI

A command-line interface for tracking LeetCode study progress, utilising the [SuperMemo-2](https://en.wikipedia.org/wiki/SuperMemo) (SM-2) spaced repetition algorithm to optimise review schedules.

<img width="940" height="567" alt="lc-track CLI help menu" src="https://github.com/user-attachments/assets/e6e6b955-2c7c-40be-9ee3-e74fc9ccad50" />

### SuperMemo-2 Confidence Levels

Select a confidence level based on your performance:

* `0` **Complete Failure** – No recall; unable to formulate a solution.
* `1` **Recognised** – Failed the problem, but the solution was understood upon review.
* `2` **Near Miss** – Failed to pass, but was very close to a functional implementation.
* `3` **Strenuous** – Correct solution, but required significant mental effort or time.
* `4` **Proficient** – Correct solution; implemented with minor hesitation or thought.
* `5` **Perfect** – Instant, effortless recall and flawless implementation.

### Sync & Backup

Users can back up their study logs using the `lc-track setup-backup` and `lc-track sync` commands. 

Configure a GitHub repository using a [Fine-grained PAT](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#fine-grained-personal-access-tokens) to serve as a remote backup for `lc-track`'s event log and program state. 

```text
[ LC-TRACK SYNC SETUP ]

Prerequisites:
1. A GitHub repository (e.g., 'lc-track-backup')
2. A Fine-Grained PAT with 'Contents: Read & Write' permissions
   for the specified repository
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
ruff check
