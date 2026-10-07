"""Integration check for staff journey assignment. Requires a seeded PostgreSQL DB.

Run from backend: python tests_journey_assignment.py
All test rows are rolled back after the check.
"""
from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.core.dependencies import get_current_user
from app.main import app
from app.models import Patient, Pathway, PathwayStep


def main():
    with engine.connect() as connection:
        outer = connection.begin()
        db = Session(bind=connection, join_transaction_mode="create_savepoint")
        patient_ids = [uuid4(), uuid4()]
        try:
            pathway = db.query(Pathway).filter(Pathway.status == "ACTIVE").first()
            assert pathway is not None, "Seed an active pathway before running this check"
            expected_steps = db.query(PathwayStep).filter(PathwayStep.pathway_id == pathway.id).count()
            assert expected_steps > 0
            now = datetime.now(timezone.utc)
            for number, patient_id in enumerate(patient_ids):
                db.add(Patient(
                    id=patient_id, patient_reference=f"ASSIGN-TEST-{patient_id.hex[:12]}",
                    first_name="Journey", last_name=f"Test{number}",
                    date_of_birth=date(1990, 1, 1), gender="other",
                    created_at=now, updated_at=now,
                ))
            db.commit()

            def test_db():
                with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                    yield session

            def test_user(request: Request):
                role = request.headers.get("X-Test-Role", "CARE_COORDINATOR")
                patient_id = patient_ids[1] if request.headers.get("X-Test-Other") else patient_ids[0]
                return SimpleNamespace(role=role, patient_id=patient_id)

            app.dependency_overrides[get_db] = test_db
            app.dependency_overrides[get_current_user] = test_user
            with TestClient(app) as client:
                base = f"/api/v1/patients/{patient_ids[0]}/journeys"
                patient_headers = {"X-Test-Role": "PATIENT"}
                assert client.get("/api/v1/me/journeys", headers=patient_headers).json() == []
                assert client.get("/api/v1/journeys/available-pathways", headers=patient_headers).status_code == 403
                assert client.post(base, json={"pathway_id": str(pathway.id)}, headers=patient_headers).status_code == 403

                response = client.post(base, json={"pathway_id": str(pathway.id), "priority": "HIGH"})
                assert response.status_code == 201, response.text
                journey = response.json()
                assert journey["pathway_name"] == pathway.name
                assert journey["priority"] == "HIGH"
                assert client.post(base, json={"pathway_id": str(pathway.id)}).status_code == 409
                assert client.post(base, json={"pathway_id": str(uuid4())}).status_code == 422

                own = client.get("/api/v1/me/journeys", headers=patient_headers)
                assert own.status_code == 200 and len(own.json()) == 1
                assert own.json()[0]["id"] == journey["id"]
                assert own.json()[0]["pathway_name"] == pathway.name

                steps = client.get(f"/api/v1/me/journeys/{journey['id']}/steps", headers=patient_headers)
                assert steps.status_code == 200, steps.text
                assert len(steps.json()) == expected_steps
                assert steps.json()[0]["name"] and steps.json()[0]["status"] == "READY"
                assert steps.json()[0]["sequence_number"] <= steps.json()[-1]["sequence_number"]

                other_headers = {"X-Test-Role": "PATIENT", "X-Test-Other": "1"}
                assert client.get("/api/v1/me/journeys", headers=other_headers).json() == []
                assert client.get(f"/api/v1/me/journeys/{journey['id']}", headers=other_headers).status_code == 404

                evaluation = client.post(f"/api/v1/journeys/{journey['id']}/evaluate")
                assert evaluation.status_code == 200, evaluation.text
                reasons = [result.get("reason") for step in evaluation.json()["steps"] for result in step.get("dependency_results", [])]
                assert "Source step is not present in journey" not in reasons
            print("PASS: staff assignment, duplicate guard, patient visibility, step details, ownership, evaluation")
        finally:
            app.dependency_overrides.clear()
            db.close()
            outer.rollback()


if __name__ == "__main__":
    main()
