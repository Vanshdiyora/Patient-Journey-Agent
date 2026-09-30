from typing import Any, TypedDict

class SupervisorState(TypedDict, total=False):
    journey_id: str
    iteration: int
    context: dict[str, Any]
    decision: dict[str, Any]
    result: dict[str, Any]
    calls: list[dict[str, Any]]
    status: str
