from dataclasses import dataclass

@dataclass
class JourneyException:
    exception_type: str
    title: str
    description: str
    severity: str
    recommended_action: str
