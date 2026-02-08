
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple


from .constants import TMP_EVENT_HISTORY, BACKUP_EVENT_HISTORY, LOCAL_EVENT_HISTORY
from .ds import AddEntryEvent, BaseEvent, RmEntryEvent
from .utility import SM2
from . import access

def merge_event_logs(hist1 : Path, hist2 : Path) -> List[BaseEvent]:
    # Load both event histories into memory
    events_local : List[dict] = load_event_log(hist1)
    events_backup : List[dict] = load_event_log(hist2)

    # Merge the two into a single list of unique events, sorted by ts
    combined_events = list({event.uuid: event for event in events_backup + events_local}.values())
    combined_events.sort(key=lambda x : x.ts)

    return combined_events

def load_event_log(path : Path) -> List[BaseEvent]:
    if not path.exists():
        return []
    
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1): 
            line = line.strip() 
            if not line:
                continue
            try:
                events.append(jsonl_to_event(json.loads(line)))

            except json.JSONDecodeError as exc:
                raise Exception(f"Failed to parse ln {ln} of {f}: {exc}") 

    return events            

def jsonl_to_event(jsonl : Dict[str, Any]) -> BaseEvent:
    if jsonl['EVENT_TYPE'] == "ADD_ENTRY":
        return AddEntryEvent.from_dict(jsonl)
    elif json['EVENT_TYPE'] == "RM_ENTRY":
        return RmEntryEvent.from_dict(jsonl)

def write_event_log(loc : Path, event_history : List[BaseEvent]) -> None:
    with open(loc, 'w', encoding="utf-8") as f:
        for event in event_history: 
            line = json.dumps(event.to_dict())
            f.write(line + '\n')

def update_state_from_local_event_history() -> None:
    """
    Steps:
    1. Clear the entries database table
    2. Run through the events stored under LOCAL_EVENT_HISTORY updating the entries database table
    3. Wipe the problem state for all problems
    4. Run through every entry within entries in chronological order to derive the correct state of each problem
    """

    with access.get_db_connection() as con:
        access.clear_entries_table(con)

        # 1. Load all events from the local version of the event history
        events = load_event_log(LOCAL_EVENT_HISTORY)    

        # 2. Process all events in chronological order
        for event in events:
            access.process_event(con, event)

        print(f"All events processed")
        
        # 3. Update the state of all problems based of the entries under the entries table
        entries = access.get_all_entries(con) 

        sm2_states : Dict[int, Tuple[int, float, int]] = {} # problem_id -> SM2 state (n, EF, I, last_review_ts, next_review_ts)

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


