from dataclasses import dataclass
from typing import Any
from datetime import datetime

@dataclass
class EvidenceEvent:
    event_id: str
    event_type: str
    source: str
    observed_at: datetime
    payload: dict[str, Any]
