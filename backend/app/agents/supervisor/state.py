from typing import Any, TypedDict

class SupervisorState(TypedDict, total=False):
    journey_id: str
    run_id: str
    iteration: int
    context: dict[str, Any]
    decision: dict[str, Any]
    result: dict[str, Any]
    outcomes: list[dict[str, Any]]
    calls: list[dict[str, Any]]
    status: str
    mode: str                      # AI | RULES_ONLY
    warnings: list[str]
    attempted: list[str]           # step ids already acted on in this run
    failed_steps: list[str]
    agent_completed: list[str]     # step ids completed by a verified agent action
    ji_done: bool
