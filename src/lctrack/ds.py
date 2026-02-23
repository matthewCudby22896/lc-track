
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any, ClassVar, Final, Self

UUID = str

@dataclass
class Entry:
    uuid : UUID
    problem_id : int
    confidence: int
    ts : int

    @classmethod
    def from_row(cls, row: tuple) -> Self:
        return Entry(
            uuid=row[0],
            problem_id=row[1],
            confidence=row[2],
            ts=row[3]
        )

    def to_row(self) -> tuple[str, int, int, int]:
        return (self.uuid, self.problem_id, self.confidence, self.ts)

@dataclass
class BaseEvent(ABC):  # Inherit from ABC
    uuid: UUID
    ts: int

    # This forces subclasses to define EVENT_TYPE
    @property
    @abstractmethod
    def EVENT_TYPE(self) -> str:
        pass

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["EVENT_TYPE"] = self.EVENT_TYPE
        return data


@dataclass
class AddEntryEvent(BaseEvent):
    EVENT_TYPE: ClassVar[Final[str]] = "ADD_ENTRY"

    entry_uuid: UUID
    problem_id: int
    confidence: int

    @classmethod
    def from_dict(cls, _dict : dict) -> Self:
        return AddEntryEvent(
            _dict['uuid'],
            _dict['ts'],
            _dict['entry_uuid'],
            _dict['problem_id'],
            _dict['confidence']
        )

@dataclass
class RmEntryEvent(BaseEvent):
    EVENT_TYPE: ClassVar[Final[str]] = "RM_ENTRY"
    target_entry_uuid: UUID

    @classmethod
    def from_dict(cls, _dict : dict) -> Self:
        return RmEntryEvent(
            _dict['uuid'],
            _dict['ts'],
            _dict['target_entry_uuid']
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

