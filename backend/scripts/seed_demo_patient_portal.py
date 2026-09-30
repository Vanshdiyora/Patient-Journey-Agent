"""Create four synthetic patient portal accounts and journey examples.

Safe to rerun: records use stable IDs/references and are inserted only when
missing. Run the patient email migration first:

    python scripts/seed_demo_patient_portal.py

This is local demo data. All generated accounts use the shared demo password
and store only a bcrypt hash in PostgreSQL.
"""
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.core.passwords import hash_password, verify_password
from app.models import ExceptionRecord, Journey, JourneyStep, Patient, PatientEvent, Pathway, PathwayStep, User


NOW = datetime.now(timezone.utc)
DEMO_NAMESPACE = "https://carepath.example.test/demo-patient/2026/"

PATIENTS = [
    {
        "number": 1,
        "reference": "DEMO-PT-2026-0001",
        "first_name": "Maya",
        "last_name": "Chen",
        "email": "maya.chen.0001@patient-demo.example.test",
        "dob": date(1954, 4, 12),
        "gender": "Female",
        "pathway": "CHF-DISCHARGE",
        "priority": "HIGH",
        "days_ago": 2,
        "completed": {"DISCHARGE-MEDS", "WEIGHT"},
        "ready": "PHONE-72H",
        "blocked": None,
        "result_evidence": ("LAB-7D", "LAB_RESULT_AVAILABLE"),
    },
    {
        "number": 2,
        "reference": "DEMO-PT-2026-0002",
        "first_name": "Robert",
        "last_name": "Hayes",
        "email": "robert.hayes.0002@patient-demo.example.test",
        "dob": date(1962, 11, 3),
        "gender": "Male",
        "pathway": "COPD-EXAC",
        "priority": "MEDIUM",
        "days_ago": 3,
        "completed": {"MED-RECON", "ACTION-PLAN"},
        "ready": None,
        "blocked": "SMOKING",
        "result_evidence": None,
    },
    {
        "number": 3,
        "reference": "DEMO-PT-2026-0003",
        "first_name": "Aisha",
        "last_name": "Rahman",
        "email": "aisha.rahman.0003@patient-demo.example.test",
        "dob": date(1970, 6, 27),
        "gender": "Female",
        "pathway": "DIAB-ANNUAL",
        "priority": "MEDIUM",
        "days_ago": 4,
        "completed": {"A1C", "RENAL"},
        "ready": "MED-REVIEW",
        "blocked": None,
        "result_evidence": ("A1C", "LAB_RESULT_AVAILABLE"),
    },
    {
        "number": 4,
        "reference": "DEMO-PT-2026-0004",
        "first_name": "Daniel",
        "last_name": "Brooks",
        "email": "daniel.brooks.0004@patient-demo.example.test",
        "dob": date(1958, 2, 15),
        "gender": "Male",
        "pathway": "ORTHO-TKA",
        "priority": "HIGH",
        "days_ago": 4,
        "completed": {"PREOP-REVIEW", "SURGERY", "DISCHARGE", "WOUND"},
        "ready": "PHYSIO",
        "blocked": None,
        "result_evidence": ("WOUND", "CLINICAL_REVIEW_COMPLETED"),
    },
]


def stable_id(kind: str, number: int, suffix: str = "") -> UUID:
    return uuid5(NAMESPACE_URL, f"{DEMO_NAMESPACE}{kind}/{number:04d}/{suffix}")


def ensure_user(db, patient: Patient, profile: dict) -> None:
    user = db.query(User).filter(User.patient_id == patient.id).first()
    by_email = db.query(User).filter(User.email == profile["email"]).first()
    if by_email and by_email.patient_id not in (None, patient.id):
        raise ValueError(f"Email {profile['email']} is already linked to another patient")
    user = user or by_email
    if user:
        user.email = profile["email"]
        user.display_name = f"{profile['first_name']} {profile['last_name']} (Patient)"
        user.role = "PATIENT"
        user.patient_id = patient.id
        user.is_active = True
        if not verify_password("Test@123", user.password_hash):
            user.password_hash = hash_password("Test@123")
        user.updated_at = NOW
    else:
        db.add(User(
            id=stable_id("user", profile["number"]),
            email=profile["email"],
            password_hash=hash_password("Test@123"),
            display_name=f"{profile['first_name']} {profile['last_name']} (Patient)",
            role="PATIENT",
            patient_id=patient.id,
            is_active=True,
            created_at=NOW,
            updated_at=NOW,
        ))


def seed_one(db, profile: dict) -> None:
    patient_id = stable_id("patient", profile["number"])
    patient = db.query(Patient).filter(Patient.patient_reference == profile["reference"]).first()
    if patient is None:
        patient = Patient(
            id=patient_id,
            patient_reference=profile["reference"],
            first_name=profile["first_name"],
            last_name=profile["last_name"],
            email=profile["email"],
            date_of_birth=profile["dob"],
            gender=profile["gender"],
            created_at=NOW,
            updated_at=NOW,
        )
        db.add(patient)
        db.flush()
    else:
        patient.email = profile["email"]

    ensure_user(db, patient, profile)

    journey_id = stable_id("journey", profile["number"])
    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    pathway = db.query(Pathway).filter(Pathway.code == profile["pathway"], Pathway.status == "ACTIVE").first()
    if not pathway:
        raise ValueError(f"No active pathway found for {profile['pathway']}")
    started_at = NOW - timedelta(days=profile["days_ago"])
    journey = journey or db.query(Journey).filter(
        Journey.patient_id == patient.id, Journey.pathway_id == pathway.id
    ).first()
    if journey is None:
        journey = Journey(
            id=journey_id,
            patient_id=patient.id,
            pathway_id=pathway.id,
            pathway_version=pathway.version,
            status="BLOCKED" if profile["blocked"] else "ACTIVE",
            priority=profile["priority"],
            started_at=started_at,
            target_completion_at=started_at + timedelta(days=45),
            completed_at=None,
            created_at=NOW,
            updated_at=NOW,
        )
        db.add(journey)
        db.flush()

    pathway_steps = db.query(PathwayStep).filter(PathwayStep.pathway_id == pathway.id).order_by(PathwayStep.sequence_number).all()
    if not pathway_steps:
        raise ValueError(f"No steps found for active pathway {profile['pathway']}")
    existing_steps = {
        row.pathway_step_id: row
        for row in db.query(JourneyStep).filter(JourneyStep.journey_id == journey.id).all()
    }
    for pathway_step in pathway_steps:
        row = existing_steps.get(pathway_step.id)
        if row:
            continue
        completed = pathway_step.code in profile["completed"]
        ready = pathway_step.code == profile["ready"]
        blocked = pathway_step.code == profile["blocked"]
        completed_at = started_at + timedelta(days=max(0, pathway_step.due_after_days or 0)) if completed else None
        db.add(JourneyStep(
            id=stable_id("step", profile["number"], pathway_step.code),
            journey_id=journey.id,
            pathway_step_id=pathway_step.id,
            status="COMPLETED" if completed else "BLOCKED" if blocked else "READY" if ready else "PENDING",
            due_at=started_at + timedelta(days=pathway_step.due_after_days or 0),
            started_at=started_at if completed else None,
            completed_at=completed_at,
            block_reason="Required result evidence is missing" if blocked else None,
            last_evaluated_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        ))

    # Persist step rows before creating exceptions that reference their IDs.
    db.flush()

    # Add simple synthetic audit events for completed steps and current result
    # evidence. IDs are stable so this seed remains idempotent.
    existing_event_ids = {
        row.external_event_id
        for row in db.query(PatientEvent.external_event_id).filter(PatientEvent.journey_id == journey.id).all()
    }
    for index, step_code in enumerate(sorted(profile["completed"])):
        external_id = f"demo-patient-{profile['number']:04d}-complete-{step_code.lower()}"
        if external_id in existing_event_ids:
            continue
        event_time = started_at + timedelta(hours=12 + index * 6)
        db.add(PatientEvent(
            id=stable_id("event", profile["number"], f"complete-{step_code}"),
            patient_id=patient.id,
            journey_id=journey.id,
            event_type="STEP_COMPLETED",
            source="DEMO_SEED",
            external_event_id=external_id,
            event_time=event_time,
            payload={"step_code": step_code, "step_completed": True, "verified": True, "synthetic_demo": True},
            processed=True,
            created_at=event_time,
        ))
    evidence = profile["result_evidence"]
    if evidence:
        step_code, event_type = evidence
        external_id = f"demo-patient-{profile['number']:04d}-evidence-{step_code.lower()}"
        if external_id not in existing_event_ids:
            event_time = NOW - timedelta(hours=8)
            db.add(PatientEvent(
                id=stable_id("event", profile["number"], f"evidence-{step_code}"),
                patient_id=patient.id,
                journey_id=journey.id,
                event_type=event_type,
                source="DEMO_SEED",
                external_event_id=external_id,
                event_time=event_time,
                payload={"step_code": step_code, "result_available": True, "synthetic_demo": True},
                processed=True,
                created_at=event_time,
            ))

    if profile["blocked"]:
        exception_id = stable_id("exception", profile["number"])
        if not db.query(ExceptionRecord).filter(ExceptionRecord.id == exception_id).first():
            blocked_step = next(s for s in pathway_steps if s.code == profile["blocked"])
            step_row = existing_steps.get(blocked_step.id)
            step_row_id = step_row.id if step_row else stable_id("step", profile["number"], blocked_step.code)
            db.add(ExceptionRecord(
                id=exception_id,
                journey_id=journey.id,
                journey_step_id=step_row_id,
                severity="MEDIUM",
                exception_type="DEPENDENCY_BLOCKED",
                title="Required result evidence is missing",
                description="Synthetic demo record: the pathway is waiting for required evidence before this step can proceed.",
                status="OPEN",
                recommended_action="Review the missing evidence and coordinate the next step.",
                created_at=NOW,
                resolved_at=None,
            ))


def main() -> None:
    db = SessionLocal()
    try:
        for patient_profile in PATIENTS:
            seed_one(db, patient_profile)
        db.commit()
        print("Seeded or confirmed 4 synthetic patient portal accounts and journeys.")
        for patient_profile in PATIENTS:
            print(
                f"{patient_profile['reference']} | {patient_profile['email']} | "
                f"password=Test@123 | {patient_profile['pathway']}"
            )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
