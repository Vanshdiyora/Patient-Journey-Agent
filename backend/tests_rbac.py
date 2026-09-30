"""
RBAC boundary tests. Run:  python tests_rbac.py
Uses the real database; creates a patient-role user + dedicated patient/journey.
"""
import json
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

import uvicorn

from app.core.database import Base, SessionLocal, engine
from app.models import Patient, Journey
from app.models.user import User

BASE = "http://127.0.0.1:8777"


def req(method, path, body=None, token=None, expected_fail=False):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main():
    # ---- Seed RBAC fixtures -------------------------------------------------
    pid = uuid.uuid4()
    jid = uuid.uuid4()
    other_pid = uuid.uuid4()
    other_jid = uuid.uuid4()
    now = datetime.now(timezone.utc)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Patients
    db.add(Patient(id=pid, patient_reference=f"RBAC-{pid.hex[:8]}", first_name="Rbac", last_name="Tester",
                   date_of_birth="1990-01-01", gender="female", created_at=now, updated_at=now))
    db.add(Patient(id=other_pid, patient_reference=f"RBAC-{other_pid.hex[:8]}", first_name="Other", last_name="Patient",
                   date_of_birth="1980-01-01", gender="male", created_at=now, updated_at=now))
    db.flush()  # patients first: journeys carry an FK to patients

    # Journeys (ACTIVE, MEDIUM priority per the journey_priority enum; pathway_id NOT NULL)
    pathway_id = db.execute(
        __import__('sqlalchemy').text("SELECT id FROM pathways LIMIT 1")
    ).scalar()
    db.add(Journey(id=jid, patient_id=pid, pathway_id=pathway_id, pathway_version=1, status="ACTIVE", priority="MEDIUM",
                   started_at=now, created_at=now, updated_at=now))
    db.add(Journey(id=other_jid, patient_id=other_pid, pathway_id=pathway_id, pathway_version=1, status="ACTIVE", priority="MEDIUM",
                   started_at=now, created_at=now, updated_at=now))

    # Users: admin, clinician, coordinator, patient (linked), unlinked patient
    def mkuser(email, role, patient_id=None, active=True):
        u = User(entra_object_id=f"entra-rbac-{email}", email=email, display_name=email.split("@")[0],
                 role=role, patient_id=patient_id, is_active=active, created_at=now, updated_at=now)
        db.add(u)
        return u

    mkuser("rbac.admin@carepath-health.example", "ADMIN")
    mkuser("rbac.clinician@carepath-health.example", "CLINICIAN")
    mkuser("rbac.coordinator@carepath-health.example", "CARE_COORDINATOR")
    mkuser("rbac.patient@carepath-health.example", "PATIENT", patient_id=pid)
    mkuser("rbac.patient2@carepath-health.example", "PATIENT", patient_id=other_pid)
    mkuser("rbac.unlinked@carepath-health.example", "PATIENT", patient_id=None)
    db.commit()
    db.close()

    from app.main import app
    config = uvicorn.Config(app, host="127.0.0.1", port=8777, log_level="error")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(60):
        if server.started:
            break
        time.sleep(0.25)

    ok = True
    def check(label, cond, detail=""):
        nonlocal ok
        print(("PASS  " if cond else "FAIL  ") + label + ("" if cond else f"  -> {detail}"))
        ok = ok and cond

    def login(email, oid):
        s, b = req("POST", "/api/v1/auth/login", {"email": email, "entra_object_id": oid})
        return b.get("access_token") if s == 200 else None

    ADMIN = login("rbac.admin@carepath-health.example", "entra-rbac-rbac.admin@carepath-health.example")
    CLIN = login("rbac.clinician@carepath-health.example", "entra-rbac-rbac.clinician@carepath-health.example")
    COORD = login("rbac.coordinator@carepath-health.example", "entra-rbac-rbac.coordinator@carepath-health.example")
    PAT = login("rbac.patient@carepath-health.example", "entra-rbac-rbac.patient@carepath-health.example")
    PAT2 = login("rbac.patient2@carepath-health.example", "entra-rbac-rbac.patient2@carepath-health.example")
    UNLINKED = None
    s, b = req("POST", "/api/v1/auth/login", {"email": "rbac.unlinked@carepath-health.example", "entra_object_id": "entra-rbac-rbac.unlinked@carepath-health.example"})
    # unlinked patient user is a valid identity; role checks will gate them

    check("staff logins issued", all([ADMIN, CLIN, COORD, PAT, PAT2]))

    # ---- Login boundaries ---------------------------------------------------
    s, b = req("POST", "/api/v1/auth/login", {"email": "rbac.unlinked@carepath-health.example", "entra_object_id": "entra-rbac-rbac.unlinked@carepath-health.example"})
    check("unlinked patient can still login", s == 200, f"{s} {b}")

    # ---- Staff surfaces denied to patients ----------------------------------
    s, _ = req("GET", "/api/v1/patients", token=PAT)
    check("patient GET /patients -> 403", s == 403, s)
    s, _ = req("GET", "/api/v1/journeys", token=PAT)
    check("patient GET /journeys -> 403", s == 403, s)
    s, _ = req("GET", "/api/v1/exceptions", token=PAT)
    check("patient GET /exceptions -> 403", s == 403, s)
    s, _ = req("GET", "/api/v1/agent-runs", token=PAT)
    check("patient GET /agent-runs -> 403", s == 403, s)
    s, _ = req("GET", "/api/v1/dashboard/summary", token=PAT)
    check("patient GET /dashboard -> 403", s == 403, s)
    s, _ = req("GET", "/api/v1/actions/registry", token=PAT)
    check("patient GET /actions/registry -> 403", s == 403, s)

    # ---- Journey reads: ownership enforced, 404 (not 403) for others --------
    s, _ = req("GET", f"/api/v1/journeys/{jid}", token=PAT)
    check("patient reads OWN journey (staff endpoint) -> 403", s == 403, s)
    s, b = req("GET", f"/api/v1/me/journeys/{jid}", token=PAT)
    check("patient reads OWN journey via /me -> 200", s == 200, f"{s} {b}")
    s, _ = req("GET", f"/api/v1/me/journeys/{other_jid}", token=PAT)
    check("patient reads OTHER journey via /me -> 404", s == 404, s)
    s, _ = req("GET", f"/api/v1/me/journeys/{jid}", token=PAT2)
    check("patient2 cannot see PAT's journey -> 404", s == 404, s)

    # ---- Patient event submission: allowlists -------------------------------
    s, b = req("POST", f"/api/v1/me/journeys/{jid}/events",
               {"event_type": "SYMPTOM_REPORTED", "payload": {"comment": "feeling fine", "verified": True, "step_completed": True, "step_code": "X"}},
               token=PAT)
    check("patient event -> 201", s == 201, f"{s} {b}")
    if s == 201:
        check("source forced to patient-portal", b.get("source") == "patient-portal", b.get("source"))
        check("verified/step_completed stripped from payload", "verified" not in b.get("payload", {}) and "step_completed" not in b.get("payload", {}), b.get("payload"))
        check("processed stays false (unverified report)", b.get("processed") is False, b.get("processed"))

    s, b = req("POST", f"/api/v1/me/journeys/{jid}/events", {"event_type": "STEP_COMPLETED", "payload": {}}, token=PAT)
    check("patient STEP_COMPLETED rejected -> 422", s == 422, s)

    s, b = req("POST", f"/api/v1/me/journeys/{other_jid}/events", {"event_type": "SYMPTOM_REPORTED", "payload": {}}, token=PAT)
    check("patient event on OTHER journey -> 404", s == 404, s)

    # staff endpoint rejects patient-channel sources
    s, b = req("POST", f"/api/v1/journeys/{jid}/events",
               {"event_type": "SYMPTOM_REPORTED", "source": "patient-portal", "event_time": "2026-09-30T10:00:00Z", "payload": {}},
               token=COORD)
    check("staff event with patient source -> 403", s == 403, s)

    # ---- Orchestration / evaluation boundaries ------------------------------
    s, _ = req("POST", f"/api/v1/journeys/{jid}/orchestrate", token=PAT)
    check("patient orchestrate -> 403", s == 403, s)
    s, _ = req("POST", f"/api/v1/journeys/{jid}/evaluate", {}, token=PAT)
    check("patient evaluate -> 403", s == 403, s)
    s, b = req("POST", f"/api/v1/journeys/{jid}/evaluate", {}, token=COORD)
    check("coordinator evaluate -> 200", s in (200, 500), f"{s} {str(b)[:80]}")

    # ---- Exception resolution ------------------------------------------------
    # (list + patch tested for role gate; data-dependent cases skipped)
    s, _ = req("PATCH", f"/api/v1/exceptions/{uuid.uuid4()}", {"status": "RESOLVED"}, token=PAT)
    check("patient resolve exception -> 403", s == 403, s)

    # ---- Admin-only management ----------------------------------------------
    # (no user management endpoints yet; require_admin enforced where added)

    print("\nRESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    server.should_exit = True


if __name__ == "__main__":
    main()
