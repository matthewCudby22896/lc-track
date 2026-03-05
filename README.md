# lc-track CLI

A CLI tool for tracking LeetCode problem study that uses the [SuperMemo2](https://en.wikipedia.org/wiki/SuperMemo) (SM2) spaced repetition algorithm to determine the optimal time at which to re-review the problem. 

<img width="940" height="567" alt="image" src="https://github.com/user-attachments/assets/e6e6b955-2c7c-40be-9ee3-e74fc9ccad50" />

### SuperMemo-2 Confidence

Choose confidence based of the following description:

* `0` **Total Blackout** - You had no idea.
* `1` **Familiar** - Wrong answer, but you recognised the solution.
* `2` **Easy to Remember** - Wrong answer, but you felt you *should* have known it.
* `3` **Hard** - Correct, but it took significant mental effort.
* `4` **Hesitant** - Correct, but you had to think for a moment.
* `5` **Perfect** - Instant recall.

### Sync & Backup

Users can backup their log of study via the `lc-track setup-backup` and `lc-track sync` commands. 

`lc-track setup-backup` walks the user through the two step process of assigning a remote GitHub repository to use as a remote backup of the event log. ALl that is required is the name of the backup repo, and a [Personal Access Token (PAT)](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#fine-grained-personal-access-tokens) with the correct permissions:

```
        [ LC-TRACK SYNC SETUP ]

        Prerequisites:
        1. A GitHub repository (e.g., 'lc-track-backup')
        2. A Fine-Grained PAT with 'Contents: Read & Write' permissions
        for the given repository
```

#### A Note on the Event Log & Local-remote Synchronisation

`lc-track` maintains a log of `ADD_ENTRY` and `RM_ENTRY` events. Each event is uniquely identified by a `UUID` and stored within an append-only local event log.

When `lc-track sync` is executed, the following synchronisation protocol occurs:

1. Remote Fetch: The latest version of the remote event log is pulled to the local system.
2. Deduplication and Merge: Local and remote logs are merged. Events are deduplicated via UUID, and the resulting set is sorted chronologically by timestamp.
3. Remote Update: The unified event log is pushed back to the remote repository.
4. State Reconstruction: The local `entries` table is cleared and rebuilt from the merged event log:
    * `ADD_ENTRY`: Creates an entry with the specified `UUID`, `problem_slug`, and `confidence` level.
    * `RM_ENTRY`: Deletes the entry associated with the `target_entry_uuid` if it exists; otherwise, the event is ignored.
5. Algorithm Recalculation: The SM-2 state for every affected problem is recalculated by processing the reconstructed entries in sequential order.

### Development Commands I Forget

```shell
# Run the CLI directly via Python without installing the package
python3 -m src.lc.track

# Install the project in editable (development) mode
pip3 install -e .

# Run static type checking
mypy

# Run linter
ruff check
```
