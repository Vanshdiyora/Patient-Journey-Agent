from dataclasses import dataclass
from typing import Any

@dataclass
class StepEvaluation:
    step_id: str
    status: str
    ready: bool
    blocked: bool
    reason: str | None = None
    dependency_results: list[dict[str, Any]] | None = None
