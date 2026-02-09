# lc-track CLI

A CLI tool for tracking LeetCode problem completions that uses the [SuperMemo2](https://en.wikipedia.org/wiki/SuperMemo) (SM2) spaced repetition algorithm to determine the optimal time at which to re-review the problem. 

**`lc-track`** removes the burden of deciding which LeetCode problem to study by randomly choosing problems for study from the active study set; And temporarily removing studied problems for a time period determined by the SM-2 algorithm (and the users confidence) in a manner that optimises for maximum retention.

### FEATURES

#### Key Commands

Add and remove LC problems from the _active study set_ via:

```
lc-track activate <problem-id>
lc-track deactivate <problem-id>
```

Select a random problem from the _active study set_ via:

```shell
lc-track study
```

Show the details of an LC problem:
```shell
lc-track details 
```

Record the completion of an LC problem via:
```shell
lc-track add-entry <problem-id> <confidence [0-5]>
```

Choose confidence based of the following description:

* `0` **Total Blackout** - You had no idea.
* `1` **Familiar** - Wrong answer, but you recognised the solution.
* `2` **Easy to Remember** - Wrong answer, but you felt you *should* have known it.
* `3` **Hard** - Correct, but it took significant mental effort.
* `4` **Hesitant** - Correct, but you had to think for a moment.
* `5` **Perfect** - Instant recall.

This will provide a `uuid` for the entry:

```shell
Entry saved: 3c18c236-8293-4d5b-ad9f-cccede233819 <-- UUID
LC1. Two Sum [Easy]
Confidence: 4
Streak: 1
Next Review: 2026-02-10 19:50
```
Remove an erroneous entry via:
```shell
lc-track rm-entry <entry-uuid>
```
See all previous entries (those added and not since removed) via:
```shell
lc-track log
```

#### Additional Commands

List all problems currently in the active study set.
```shell
lc-track ls-active
```

List all problems, within the active study set, currently due for review.
```shell
lc-track ls-review
```

#### Sync & Backup

Users can secure their study history and enable multi-device synchronisation using the following commands:
```shell
lc-track setup-backup  # Initialise access to a remote GitHub repository
lc-track sync          # Execute a two-way synchronisation of the event history
```

The configuration process guides the user through establishing a GitHub repository with the necessary access permissions via a [Personal Access Token (PAT)](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#fine-grained-personal-access-tokens). This repository serves as a remote store for the _event log_ from which lc-track's program state can be derived.

For users wishing to restore an existing history to a new environment, following the same same steps will sync their local state with that of the remote.

##### A note on event history & local-remote synchronisation

`lc-track` maintains a comprehensive history of `ADD_ENTRY` and `RM_ENTRY` events. Each event is uniquely identified by a UUID and stored within an append-only event log.

When `lc-track sync` is executed, the following synchronisation protocol occurs:

1. Remote Fetch: The latest version of the remote event log is pulled to the local system.
2. Deduplication and Merge: Local and remote logs are merged. Duplicate events are removed based on their UUID, and the resulting set is sorted chronologically by timestamp.
3. Remote Update: The unified event log is pushed back to the remote repository.
4. State Reconstruction: The local `entries` table is cleared and rebuilt from the merged event log:
    * `ADD_ENTRY`: Creates an entry with the specified UUID, problem ID, and confidence level.
    * `RM_ENTRY`: Deletes the entry associated with the `target_entry_uuid` if it exists; otherwise, the event is ignored.
5. Algorithm Recalculation: The SM-2 state for every affected problem is recalculated by processing the reconstructed entries in sequential order.

This ensures that the local environment perfectly reflects the global state defined by the synchronised event history, regardless of which device originally authored the events.
