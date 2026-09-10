import itertools
from collections import deque
from typing import Optional

from config import MAX_QUERY_LOG_SIZE

_log = deque(maxlen=MAX_QUERY_LOG_SIZE)
_counter = itertools.count(1)


def record(question: str, latency_ms: float, status: str) -> None:
    """status must be one of VALIDATED / REJECTED / FAILED."""
    _log.appendleft(
        {
            "query_id": f"q_{next(_counter):04d}",
            "question": question,
            "latency_ms": f"{latency_ms:.0f} ms",
            "status": status,
        }
    )


def recent(limit: Optional[int] = None) -> list:
    items = list(_log)
    return items[:limit] if limit else items


def average_latency_ms() -> float:
    if not _log:
        return 0.0
    total = sum(float(item["latency_ms"].split(" ")[0]) for item in _log)
    return round(total / len(_log), 1)