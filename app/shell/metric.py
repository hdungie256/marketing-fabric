from datetime import datetime

NOTE_TEXT: dict[str, str] = {}


def metric(term_id: str, value: float | int | None, freshness: datetime, *, kind: str = "count") -> None:
    raise NotImplementedError("Story 1.12")
