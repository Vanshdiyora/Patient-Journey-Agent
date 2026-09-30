import hashlib
import json

def build_idempotency_key(journey_id, step_id, action_type, payload):
    canonical = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"))
    raw = f"{journey_id}:{step_id}:{action_type}:{canonical}"
    return "PJO-" + hashlib.sha256(raw.encode()).hexdigest()
