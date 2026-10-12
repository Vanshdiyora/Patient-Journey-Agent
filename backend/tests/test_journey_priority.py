"""Active journey priority and one-active-journey-per-patient rules."""

import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.journeys import update_journey_priority
from app.api.v1.patients import patient_journeys, start_patient_journey
from app.models import Journey, Patient, Pathway, User
from app.schemas.journey import JourneyCreate, JourneyPriorityUpdate
from app.services.journey_service import start_journey_for_patient


class JourneyPriorityTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        for model in (Patient, User, Pathway, Journey):
            model.__table__.create(self.engine)
        self.db = Session(self.engine)
        now = datetime.now(timezone.utc)
        self.doctor = User(id=uuid4(), email="doctor@example.test", password_hash="x",
                           display_name="Dr Shah", role="CLINICIAN", is_active=True,
                           created_at=now, updated_at=now)
        self.other = User(id=uuid4(), email="other@example.test", password_hash="x",
                          display_name="Dr Rao", role="CLINICIAN", is_active=True,
                          created_at=now, updated_at=now)
        self.patient = Patient(id=uuid4(), patient_reference="P-1", first_name="Asha",
                               last_name="Shah", date_of_birth=date(1990, 1, 1),
                               gender="Female", assigned_clinician_id=self.doctor.id)
        self.pathway = Pathway(id=uuid4(), code="PATH-A", name="Care A", version=1,
                               status="ACTIVE", created_at=now, updated_at=now)
        self.other_pathway = Pathway(id=uuid4(), code="PATH-B", name="Care B", version=1,
                                     status="ACTIVE", created_at=now, updated_at=now)
        self.active = Journey(id=uuid4(), patient_id=self.patient.id, pathway_id=self.pathway.id,
                              pathway_version=1, status="ACTIVE", priority="MEDIUM",
                              started_at=now, created_at=now, updated_at=now)
        self.db.add_all([self.doctor, self.other, self.patient, self.pathway,
                         self.other_pathway, self.active])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_assigned_clinician_can_change_active_priority(self):
        result = update_journey_priority(self.active.id, JourneyPriorityUpdate(priority="HIGH"),
                                         self.db, self.doctor)
        self.assertEqual(result["priority"], "HIGH")
        self.assertEqual(self.db.query(Journey).filter_by(id=self.active.id).one().priority, "HIGH")
        self.assertTrue(patient_journeys(self.patient.id, 10, 0, self.db, self.doctor)["has_active_journey"])

    def test_other_clinician_cannot_change_priority(self):
        with self.assertRaises(HTTPException) as caught:
            update_journey_priority(self.active.id, JourneyPriorityUpdate(priority="LOW"),
                                    self.db, self.other)
        self.assertEqual(caught.exception.status_code, 404)

    def test_completed_priority_cannot_change(self):
        self.active.status = "COMPLETED"
        self.db.commit()
        with self.assertRaises(HTTPException) as caught:
            update_journey_priority(self.active.id, JourneyPriorityUpdate(priority="HIGH"),
                                    self.db, self.doctor)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertFalse(patient_journeys(self.patient.id, 10, 0, self.db, self.doctor)["has_active_journey"])

    def test_second_active_journey_is_rejected_even_for_another_pathway(self):
        with self.assertRaises(HTTPException) as caught:
            start_journey_for_patient(self.db, self.patient.id, self.other_pathway.id, "LOW")
        self.assertEqual(caught.exception.status_code, 409)

    def test_priority_values_are_validated(self):
        with self.assertRaises(ValidationError):
            JourneyPriorityUpdate(priority="URGENT")

    def test_admin_starts_without_setting_priority(self):
        admin = SimpleNamespace(id=uuid4(), role="ADMIN")
        data = JourneyCreate(pathway_id=self.other_pathway.id)
        with patch("app.api.v1.patients.start_journey_for_patient", return_value=self.active) as create:
            result = start_patient_journey(self.patient.id, data, self.db, admin)
        create.assert_called_once_with(self.db, self.patient.id, self.other_pathway.id, "MEDIUM", {})
        self.assertEqual(result["priority"], "MEDIUM")

    def test_admin_cannot_submit_priority(self):
        admin = SimpleNamespace(id=uuid4(), role="ADMIN")
        data = JourneyCreate(pathway_id=self.other_pathway.id, priority="HIGH")
        with self.assertRaises(HTTPException) as caught:
            start_patient_journey(self.patient.id, data, self.db, admin)
        self.assertEqual(caught.exception.status_code, 422)

    def test_admin_cannot_change_journey_priority(self):
        admin = SimpleNamespace(id=uuid4(), role="ADMIN")
        with self.assertRaises(HTTPException) as caught:
            update_journey_priority(self.active.id, JourneyPriorityUpdate(priority="HIGH"),
                                    self.db, admin)
        self.assertEqual(caught.exception.status_code, 403)

    def test_clinician_must_set_priority_when_starting(self):
        data = JourneyCreate(pathway_id=self.other_pathway.id)
        with self.assertRaises(HTTPException) as caught:
            start_patient_journey(self.patient.id, data, self.db, self.doctor)
        self.assertEqual(caught.exception.status_code, 422)

    def test_care_coordinator_cannot_start_journey(self):
        coordinator = SimpleNamespace(id=uuid4(), role="CARE_COORDINATOR")
        data = JourneyCreate(pathway_id=self.other_pathway.id)
        with self.assertRaises(HTTPException) as caught:
            start_patient_journey(self.patient.id, data, self.db, coordinator)
        self.assertEqual(caught.exception.status_code, 403)
