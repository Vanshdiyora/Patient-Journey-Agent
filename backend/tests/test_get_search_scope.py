"""Search and filter before pagination, including records beyond the first page."""

import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.admin import list_users as api_list_users
from app.api.v1.exceptions import exceptions as api_list_exceptions
from app.api.v1.journeys import list_journeys as api_list_journeys
from app.api.v1.patients import list_patients as api_list_patients
from app.llm.tool_read import (
    tool_get_patient_summary,
    tool_list_exceptions,
    tool_list_journeys,
    tool_list_users,
    tool_search_patients,
)
from app.models import ExceptionRecord, Journey, Patient, Pathway, User


class GetSearchScopeTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        for model in (Patient, User, Pathway, Journey, ExceptionRecord):
            model.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.admin = SimpleNamespace(role="ADMIN")
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def patient(self, first, last, number):
        row = Patient(id=uuid4(), patient_reference=f"P-{number:04d}",
                      first_name=first, last_name=last, date_of_birth=date(1990, 1, 1),
                      gender="F", created_at=self.now + timedelta(days=number))
        self.db.add(row)
        return row

    def test_patient_name_search_checks_records_after_first_page(self):
        target = self.patient("Shreya", "Desai", 1)
        for number in range(2, 17):
            self.patient("Other", f"Person{number}", number)
        self.db.commit()

        page = api_list_patients(search="Shreya   Desai", filter=None, limit=10, offset=0,
                                 db=self.db, user=self.admin)
        found = tool_search_patients(self.db, self.admin, {"query": "shreya desai"})
        self.assertEqual(page["total"], 1)
        self.assertEqual(page["items"][0].id, target.id)
        self.assertEqual(found["data"]["total"], 1)
        self.assertEqual(found["data"]["patients"][0]["id"], str(target.id))

    def test_journey_filter_and_assistant_pages_use_full_result_set(self):
        patient = self.patient("Shreya", "Desai", 1)
        pathway = Pathway(id=uuid4(), code="P", name="Care", version=1, status="ACTIVE")
        self.db.add(pathway)
        for number in range(30):
            self.db.add(Journey(id=uuid4(), patient_id=patient.id, pathway_id=pathway.id,
                                pathway_version=1, status="BLOCKED" if number == 0 else "ACTIVE",
                                priority="MEDIUM", started_at=self.now + timedelta(days=number),
                                updated_at=self.now + timedelta(days=number)))
        self.db.commit()

        filtered = api_list_journeys(status="BLOCKED", priority=None, limit=10, offset=0,
                                     db=self.db, user=self.admin)
        chat_filtered = tool_list_journeys(self.db, self.admin, {"status": "BLOCKED"})
        first = tool_list_journeys(self.db, self.admin, {})
        later = tool_list_journeys(self.db, self.admin, {"offset": 25})
        summary = tool_get_patient_summary(self.db, self.admin, {"patient_id": str(patient.id)})

        self.assertEqual(filtered["total"], 1)
        self.assertEqual(chat_filtered["data"]["total"], 1)
        self.assertEqual(first["data"]["total"], 30)
        self.assertEqual(len(first["data"]["journeys"]), 25)
        self.assertEqual(len(later["data"]["journeys"]), 5)
        self.assertEqual(summary["data"]["total"], 30)

    def test_user_search_checks_records_after_first_page(self):
        for number in range(30):
            self.db.add(User(id=uuid4(), email=f"user{number}@example.test", password_hash="test",
                             display_name="Shreya Desai" if number == 0 else f"Other Person{number}",
                             role="CLINICIAN", is_active=True,
                             created_at=self.now + timedelta(days=number),
                             updated_at=self.now + timedelta(days=number)))
        self.db.commit()

        page = api_list_users(role=None, search="Shreya Desai", limit=10, offset=0,
                              db=self.db, _admin=self.admin)
        found = tool_list_users(self.db, self.admin, {"search": "Shreya Desai"})
        all_users = tool_list_users(self.db, self.admin, {})
        later = tool_list_users(self.db, self.admin, {"offset": 25})

        self.assertEqual(page["total"], 1)
        self.assertEqual(found["data"]["total"], 1)
        self.assertEqual(all_users["data"]["total"], 30)
        self.assertEqual(len(later["data"]["users"]), 5)

    def test_exception_filter_checks_records_after_first_page(self):
        patient = self.patient("Shreya", "Desai", 1)
        journey = Journey(id=uuid4(), patient_id=patient.id, pathway_id=uuid4(),
                          pathway_version=1, status="ACTIVE", priority="MEDIUM",
                          started_at=self.now, updated_at=self.now)
        self.db.add(journey)
        for number in range(30):
            self.db.add(ExceptionRecord(
                id=uuid4(), journey_id=journey.id, severity="HIGH", exception_type="FOLLOW_UP",
                title=f"Exception {number}", description="Needs review",
                status="OPEN" if number == 0 else "RESOLVED",
                created_at=self.now + timedelta(days=number),
            ))
        self.db.commit()

        filtered = api_list_exceptions(status="OPEN", severity=None, limit=10, offset=0,
                                       db=self.db, user=self.admin)
        chat_filtered = tool_list_exceptions(self.db, self.admin, {"status": "OPEN"})
        all_rows = tool_list_exceptions(self.db, self.admin, {})
        later = tool_list_exceptions(self.db, self.admin, {"offset": 20})

        self.assertEqual(filtered["total"], 1)
        self.assertEqual(chat_filtered["data"]["total"], 1)
        self.assertEqual(all_rows["data"]["total"], 30)
        self.assertEqual(len(later["data"]["exceptions"]), 10)


if __name__ == "__main__":
    unittest.main()
