# lc-track CLI

A command-line interface for tracking LeetCode study progress, utilising the [SuperMemo-2](https://en.wikipedia.org/wiki/SuperMemo) (SM-2) spaced repetition algorithm to optimise review schedules.

<img width="940" height="567" alt="lc-track CLI help menu" src="https://github.com/user-attachments/assets/e6e6b955-2c7c-40be-9ee3-e74fc9ccad50" />

### SuperMemo-2 Confidence Levels

Select a confidence level based on the following criteria:

* `0` **Total Blackout** - No recall.
* `1` **Familiar** - Incorrect answer, but the solution was recognised.
* `2` **Easy to Remember** - Incorrect answer, but recalled with minimal prompting.
* `3` **Hard** - Correct answer, requiring significant mental effort.
* `4` **Hesitant** - Correct answer, requiring momentary thought.
* `5` **Perfect** - Instant, effortless recall.

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
#### Event Log & Synchronisation Protocol

`lc-track` maintains an append-only local event log of `ADD_ENTRY` and `RM_ENTRY` events, each identified by a unique `UUID`.

Executing `lc-track sync` triggers the following synchronisation protocol:

1. **Remote Fetch**: Pulls the latest remote event log to the local system.
2. **Deduplication & Merge**: Merges local and remote logs, deduplicating by UUID, and sorts the resulting set chronologically.
3. **Remote Update**: Pushes the unified event log back to the remote repository.
4. **State Reconstruction**: Clears and rebuilds the local `entries` table from the merged log:
   * `ADD_ENTRY`: Creates an entry with the specified `UUID`, `problem_slug`, and `confidence` level.
   * `RM_ENTRY`: Deletes the specified `target_entry_uuid` (ignored if the target does not exist).
5. **Algorithm Recalculation**: Sequentially processes the reconstructed entries to recalculate the SM-2 state for all affected problems.

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
