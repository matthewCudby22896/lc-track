
import json
from pathlib import Path
from typing import Any

from . import access
from .constants import LOCAL_EVENT_LOG
from .ds import AddEntryEvent, BaseEvent, RmEntryEvent
from .utility import SM2


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
        events = load_event_log(LOCAL_EVENT_LOG)

        # 2. Process all events in chronological order
        for event in events:
            access.process_event(con, event)

        print("All events processed")

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


