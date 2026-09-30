from datetime import datetime, timezone

class EscalationEngine:
    def evaluate(self, journey, step, exception_count: int = 0):
        overdue = bool(step.due_at and step.due_at < datetime.now(timezone.utc))
        critical = journey.priority == "CRITICAL"
        should_escalate = critical and overdue or exception_count >= 3
        return {"should_escalate": should_escalate, "reason": "Escalation threshold reached" if should_escalate else None}
