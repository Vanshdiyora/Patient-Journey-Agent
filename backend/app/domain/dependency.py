from dataclasses import dataclass
from typing import Any

@dataclass
class DependencyResult:
    dependency_id: str
    satisfied: bool
    blocking: bool
    reason: str
    condition_type: str
    source_step_id: str
    target_step_id: str
    evidence: list[dict[str, Any]]
