"""Patient provisioning may defer clinician assignment without granting access."""

import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi import Response
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.admin import PatientCreate, create_patient
from app.models.patient import Patient
from app.models.staff_patient_assignment import StaffPatientAssignment
from app.models.user import User


class PatientProvisioningTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        for model in (Patient, User, StaffPatientAssignment):
            model.__table__.create(self.engine)
        self.db = Session(self.engine)
        now = datetime.now(timezone.utc)
        self.admin = User(id=uuid4(), email="admin@example.test", password_hash="x",
                          display_name="Admin", role="ADMIN", is_active=True,
                          created_at=now, updated_at=now)
        self.clinician = User(id=uuid4(), email="doctor@example.test", password_hash="x",
                              display_name="Doctor", role="CLINICIAN", is_active=True,
                              created_at=now, updated_at=now)
        self.db.add_all([self.admin, self.clinician])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_patient_can_be_created_without_clinician(self):
        data = PatientCreate(first_name="Asha", last_name="Shah", email="asha@example.test",
                             date_of_birth=date(1990, 4, 5), gender="Female")
        response = Response()
        with patch("app.api.v1.admin._audit_change"), patch("app.api.v1.admin.hash_password", return_value="hashed"):
            result = create_patient(data, response, self.db, self.admin)

        patient = self.db.query(Patient).filter(Patient.email == data.email).one()
        self.assertIsNone(patient.assigned_clinician_id)
        self.assertEqual(self.db.query(StaffPatientAssignment).count(), 0)
        self.assertEqual(self.db.query(User).filter(User.patient_id == patient.id).one().role, "PATIENT")
        self.assertIsNone(result["clinician_id"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_selected_clinician_receives_patient_assignment(self):
        data = PatientCreate(first_name="Ravi", last_name="Shah", email="ravi@example.test",
                             date_of_birth=date(1990, 4, 5), gender="Male",
                             clinician_id=self.clinician.id)
        with patch("app.api.v1.admin._audit_change"), patch("app.api.v1.admin.hash_password", return_value="hashed"):
            result = create_patient(data, Response(), self.db, self.admin)

        patient = self.db.query(Patient).filter(Patient.email == data.email).one()
        self.assertEqual(patient.assigned_clinician_id, self.clinician.id)
        assignment = self.db.query(StaffPatientAssignment).one()
        self.assertEqual(assignment.patient_id, patient.id)
        self.assertEqual(result["clinician_id"], str(self.clinician.id))
