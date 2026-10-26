import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.notifications import list_notifications, mark_notification_read
from app.models import (
    InAppNotification,
    Journey,
    Patient,
    StaffPatientAssignment,
    User,
)
from app.orchestration.action_executor import ActionExecutor
from app.services.reminder_notifications import create_journey_reminder_notifications


class ReminderNotificationsTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        for model in (Patient, User, Journey, StaffPatientAssignment, InAppNotification):
            model.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.now = datetime.now(timezone.utc)

        self.patient = Patient(
            id=uuid4(),
            patient_reference="PT-TEST-1",
            first_name="Sam",
            last_name="Patient",
            email="patient@example.test",
            date_of_birth=date(1990, 1, 1),
            gender="X",
            assigned_clinician_id=None,
            created_at=self.now,
            updated_at=self.now,
        )
        self.db.add(self.patient)
        self.db.flush()

        self.patient_user = self.user("PATIENT", "patient@example.test", patient_id=self.patient.id)
        self.clinician = self.user("CLINICIAN", "clinician@example.test")
        self.coordinator = self.user("CARE_COORDINATOR", "coordinator@example.test")
        self.admin = self.user("ADMIN", "admin@example.test")
        self.unassigned_coordinator = self.user("CARE_COORDINATOR", "other@example.test")
        self.patient.assigned_clinician_id = self.clinician.id
        self.db.add(
            StaffPatientAssignment(
                id=uuid4(),
                staff_user_id=self.coordinator.id,
                patient_id=self.patient.id,
                assigned_by_user_id=self.admin.id,
                created_at=self.now,
            )
        )
        self.journey = Journey(
            id=uuid4(),
            patient_id=self.patient.id,
            pathway_id=uuid4(),
            pathway_version=1,
            status="ACTIVE",
            priority="MEDIUM",
            started_at=self.now,
            target_completion_at=None,
            completed_at=None,
            created_at=self.now,
            updated_at=self.now,
        )
        self.db.add(self.journey)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def user(self, role, email, patient_id=None):
        user = User(
            id=uuid4(),
            email=email,
            password_hash="test",
            display_name=email.split("@")[0],
            role=role,
            patient_id=patient_id,
            is_active=True,
            created_at=self.now,
            updated_at=self.now,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def test_reminder_notifies_patient_and_only_staff_with_journey_access(self):
        response = create_journey_reminder_notifications(
            self.db,
            self.journey.id,
            {"step_name": "Follow-up visit"},
        )
        self.db.commit()

        notifications = self.db.query(InAppNotification).all()
        recipient_ids = {item.user_id for item in notifications}
        self.assertTrue(response["accepted"])
        self.assertEqual(response["delivery"], "in_app")
        self.assertEqual(response["notifications_created"], 4)
        self.assertEqual(
            recipient_ids,
            {self.patient_user.id, self.clinician.id, self.coordinator.id, self.admin.id},
        )
        self.assertNotIn(self.unassigned_coordinator.id, recipient_ids)

        patient_notice = next(item for item in notifications if item.user_id == self.patient_user.id)
        staff_notice = next(item for item in notifications if item.user_id == self.coordinator.id)
        self.assertIn("Please review your care plan", patient_notice.body)
        self.assertIn("Sam Patient", staff_notice.body)

    def test_reminder_action_uses_in_app_delivery_even_when_smtp_is_enabled(self):
        execution = SimpleNamespace(
            journey_id=self.journey.id,
            status="EXECUTING",
            response_payload=None,
            error_message=None,
            completed_at=None,
        )
        with patch("app.orchestration.action_executor.settings", SimpleNamespace(email_enabled=True)):
            ActionExecutor(self.db)._run(
                execution,
                "SEND_REMINDER",
                {"step_name": "Patient education"},
            )
        self.db.commit()

        self.assertEqual(execution.status, "SUCCESS")
        self.assertEqual(execution.response_payload["delivery"], "in_app")
        self.assertEqual(execution.response_payload["notifications_created"], 4)
        self.assertEqual(self.db.query(InAppNotification).count(), 4)

    def test_notifications_are_listed_and_marked_read_only_by_their_recipient(self):
        create_journey_reminder_notifications(self.db, self.journey.id, {"step_name": "Follow-up"})
        self.db.commit()

        page = list_notifications(limit=10, offset=0, db=self.db, user=self.patient_user)
        self.assertEqual(page["total"], 1)
        self.assertEqual(page["unread"], 1)
        notification_id = UUID(page["items"][0]["id"])

        with self.assertRaises(HTTPException) as error:
            mark_notification_read(uuid4(), db=self.db, user=self.patient_user)
        self.assertEqual(error.exception.status_code, 404)

        marked = mark_notification_read(notification_id, db=self.db, user=self.patient_user)
        self.assertIsNotNone(marked["read_at"])
        updated = list_notifications(limit=10, offset=0, db=self.db, user=self.patient_user)
        self.assertEqual(updated["unread"], 0)

        other_user_page = list_notifications(limit=10, offset=0, db=self.db, user=self.unassigned_coordinator)
        self.assertEqual(other_user_page["total"], 0)


if __name__ == "__main__":
    unittest.main()
