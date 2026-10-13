"""Clinicians can browse the directory and claim only unassigned patients."""

import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.router import me as current_user_response
from app.api.v1.patients import claim_patient, get_patient, list_patients
from app.auth import UserResponse, user_response
from app.models import Journey, Patient, StaffPatientAssignment, User


class ClinicianDirectoryTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        for model in (Patient, User, StaffPatientAssignment, Journey):
            model.__table__.create(self.engine)
        self.db = Session(self.engine)
        now = datetime.now(timezone.utc)
        self.doctor = User(id=uuid4(), email="doctor@example.test", password_hash="x",
                           display_name="Dr Shah", role="CLINICIAN", is_active=True,
                           created_at=now, updated_at=now)
        self.other = User(id=uuid4(), email="other@example.test", password_hash="x",
                          display_name="Dr Rao", role="CLINICIAN", is_active=True,
                          created_at=now, updated_at=now)
        self.unassigned = Patient(id=uuid4(), patient_reference="P-1", first_name="Asha",
                                  last_name="Shah", email="asha@example.test",
                                  date_of_birth=date(1990, 1, 1), gender="Female", created_at=now)
        self.assigned = Patient(id=uuid4(), patient_reference="P-2", first_name="Ravi",
                                last_name="Rao", email="ravi@example.test",
                                date_of_birth=date(1990, 1, 1), gender="Male",
                                assigned_clinician_id=self.other.id, created_at=now)
        self.db.add_all([self.doctor, self.other, self.unassigned, self.assigned])
        for patient in (self.unassigned, self.assigned):
            self.db.add(Journey(id=uuid4(), patient_id=patient.id, pathway_id=uuid4(),
                                pathway_version=1, status="BLOCKED", priority="MEDIUM",
                                started_at=now))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def directory(self, filter_key=None):
        return list_patients(search=None, filter=filter_key, limit=10, offset=0,
                             db=self.db, user=self.doctor)

    def test_auth_responses_include_id_for_patient_profile_links(self):
        login_user = user_response(self.doctor)
        refreshed_user = current_user_response(self.doctor)
        self.assertEqual(login_user["id"], str(self.doctor.id))
        self.assertEqual(refreshed_user, login_user)
        self.assertEqual(UserResponse.model_validate(login_user).id, self.doctor.id)
        self.unassigned.assigned_clinician_id = self.doctor.id
        self.db.commit()
        my_patient = self.directory("mine")["items"][0]
        self.assertEqual(my_patient["assigned_clinician_id"], refreshed_user["id"])

    def test_directory_shows_assignments_without_other_patient_contact_details(self):
        page = self.directory()
        self.assertEqual(page["total"], 2)
        self.assertEqual(page["scope"], "directory")
        by_id = {item["id"]: item for item in page["items"]}
        self.assertIsNone(by_id[str(self.assigned.id)]["email"])
        self.assertEqual(by_id[str(self.assigned.id)]["assigned_clinician_name"], "Dr Rao")
        self.assertIsNone(by_id[str(self.unassigned.id)]["email"])
        self.assertEqual(self.directory("mine")["total"], 0)
        self.assertEqual(self.directory("blocked")["total"], 0)
        self.assertEqual(get_patient(self.assigned.id, self.db, self.other).assigned_clinician_name, "Dr Rao")
        with self.assertRaises(HTTPException) as caught:
            get_patient(self.assigned.id, self.db, self.doctor)
        self.assertEqual(caught.exception.status_code, 404)

    @patch("app.api.v1.patients.audit")
    def test_claim_adds_only_one_clinician_and_enables_care_filters(self, audit):
        result = claim_patient(self.unassigned.id, self.db, self.doctor)
        self.assertEqual(result["clinician_id"], str(self.doctor.id))
        self.assertEqual(self.db.query(StaffPatientAssignment).count(), 1)
        self.assertEqual(self.db.query(StaffPatientAssignment).one().assigned_by_user_id, self.doctor.id)
        self.assertEqual(self.directory("mine")["total"], 1)
        self.assertEqual(self.directory("blocked")["total"], 1)
        self.assertEqual(get_patient(self.unassigned.id, self.db, self.doctor).id, self.unassigned.id)
        self.assertEqual(get_patient(self.unassigned.id, self.db, self.doctor).assigned_clinician_name, "Dr Shah")
        with self.assertRaises(HTTPException) as caught:
            claim_patient(self.assigned.id, self.db, self.doctor)
        self.assertEqual(caught.exception.status_code, 409)
        with self.assertRaises(HTTPException) as caught:
            claim_patient(self.unassigned.id, self.db, self.other)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(audit.call_count, 1)
