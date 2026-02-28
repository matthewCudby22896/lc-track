
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Final, Self

UUID = str

@dataclass
class Entry:
    problem_id : int
    confidence: int
    ts : int
    uuid : str = field(default_factory=lambda : str(uuid.uuid4()))

    @classmethod
    def from_row(cls, row: tuple) -> Self:
        return cls(
            uuid=row[0],
            problem_id=row[1],
            confidence=row[2],
            ts=row[3]
        )

    def to_row(self) -> tuple[str, int, int, int]:
        return (self.uuid, self.problem_id, self.confidence, self.ts)

    @property
    def timestamp_txt(self):
        return datetime.fromtimestamp(self.ts).strftime("%Y-%m-%d %H:%M")

@dataclass
class BaseEvent(ABC):  # Inherit from ABC
    ts: int
    uuid : str = field(default_factory=lambda : str(uuid.uuid4()))

    # This forces subclasses to define EVENT_TYPE
    @property
    @abstractmethod
    def event_type(self) -> str:
        pass

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["EVENT_TYPE"] = self.event_type
        return data


@dataclass(kw_only=True)
class AddEntryEvent(BaseEvent):
    event_type: ClassVar[Final[str]] = "ADD_ENTRY"

    entry_uuid: UUID
    problem_id: int
    confidence: int

    @classmethod
    def from_dict(cls, _dict : dict) -> Self:
        return cls(
            uuid=_dict['uuid'],
            ts=_dict['ts'],
            entry_uuid=_dict['entry_uuid'],
            problem_id=_dict['problem_id'],
            confidence=_dict['confidence']
        )

@dataclass(kw_only=True)
class RmEntryEvent(BaseEvent):
    event_type: ClassVar[Final[str]] = "RM_ENTRY"
    target_entry_uuid: UUID

    @classmethod
    def from_dict(cls, _dict : dict) -> Self:
        return cls(
            uuid=_dict['uuid'],
            ts=_dict['ts'],
            target_entry_uuid=_dict['target_entry_uuid']
        )

@dataclass
class Problem:
    id: int
    slug : str
    title : str
    difficulty : int
    difficulty_txt : str
    last_review_at : int | None
    next_review_at : int
    ef : float
    i : int
    n : int
    active : bool

    @classmethod
    def from_row(cls, row: tuple) -> Self:
        return cls(
            id=row[0],
            slug=row[1],
            title=row[2],
            difficulty=row[3],
            difficulty_txt=INT_TO_DIFF[row[3]],
            last_review_at=row[4],
            next_review_at=row[5],
            ef=row[6],
            i=row[7],
            n=row[8],
            active=bool(row[9])
        )

    def next_review_txt(self) -> str:
        if not self.next_review_at:
            return "Not yet studied (due for review)"

        now = datetime.now()
        next_at = datetime.fromtimestamp(self.next_review_at)

        txt = next_at.strftime("%Y-%m-%d")

        if now >= next_at:
            return f"{txt} (due for review)"

        diff = next_at - now
        hours, _ = divmod(diff.seconds, 3600)

        return f"{txt} (due in {diff.days} days, {hours} hrs)"

    def last_review_txt(self) -> str:
        if not self.last_review_at:
            return "Never"

        now = datetime.now()
        last_at = datetime.fromtimestamp(self.last_review_at)

        txt = last_at.strftime("%Y-%m-%d")

        diff = now - last_at

        if diff.days == 0:
            # Check if it was literally just now (less than 1 hour)
            hours, _ = divmod(diff.seconds, 3600)
            if hours == 0:
                return f"{txt} (less than 1 hr ago)"
            return f"{txt} ({hours} hrs ago)"

        return f"{txt} ({diff.days} days ago)"


DIFF_TO_INT = {
    "Hard" : 2,
    "Medium" : 1,
    "Easy" : 0
}

INT_TO_DIFF = {
    2 : "Hard",
    1 : "Medium",
    0 : "Easy"
}

