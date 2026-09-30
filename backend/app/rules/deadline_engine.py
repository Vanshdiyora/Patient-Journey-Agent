from datetime import datetime, timezone

class DeadlineEngine:
    def evaluate(self, step, now: datetime | None = None):
        now = now or datetime.now(timezone.utc)
        if step.status in {"COMPLETED", "CANCELLED"}:
            return {"overdue": False, "reason": None}
        overdue = bool(step.due_at and step.due_at < now)
        return {"overdue": overdue, "reason": "Step is past its due date and requires review." if overdue else None}
