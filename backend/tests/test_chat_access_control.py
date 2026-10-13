"""Access and confirmation boundaries for the chat assistant."""

import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth import router as auth_router
from app.api.v1.admin import RoleUpdate, assign_patient, set_user_role, unassign_patient
from app.core.authorization import get_journey_scoped, scope_patient_ids
from app.llm.tools import ToolValidationError, execute_tool, get_spec, prepare_arguments, tools_for_llm
from app.llm.tool_read import tool_list_patients
from app.models import ExceptionRecord, Journey, Patient, StaffPatientAssignment, User
from app.services.chat_security import sign_pending_action, verify_pending_action
from app.services.chat_service import audit, confirm_action


class AssignedPatientScopeTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Patient.__table__.create(self.engine)
        User.__table__.create(self.engine)
        StaffPatientAssignment.__table__.create(self.engine)
        Journey.__table__.create(self.engine)
        ExceptionRecord.__table__.create(self.engine)
        self.db = Session(self.engine)
        now = datetime.now(timezone.utc)
        self.admin = User(id=uuid4(), email="admin@test.test", password_hash="x",
                          display_name="Admin", role="ADMIN", is_active=True,
                          created_at=now, updated_at=now)
        self.staff = User(id=uuid4(), email="doctor@test.test", password_hash="x",
                          display_name="Doctor", role="CLINICIAN", is_active=True,
                          created_at=now, updated_at=now)
        self.patients = [Patient(id=uuid4(), patient_reference=f"P-{i}",
                                 first_name="Test", last_name=str(i),
                                 date_of_birth=date(1990, 1, 1), gender="Other")
                         for i in range(2)]
        self.journeys = [Journey(id=uuid4(), patient_id=p.id, pathway_id=uuid4(),
                                 pathway_version=1, status="ACTIVE", priority="MEDIUM",
                                 started_at=now) for p in self.patients]
        self.db.add_all([self.admin, self.staff, *self.patients, *self.journeys])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_clinician_access_is_denied_until_assigned(self):
        self.assertEqual(scope_patient_ids(self.db, self.staff), [])
        self.assertEqual(tool_list_patients(self.db, self.staff, {})["data"]["total"], 0)
        with self.assertRaises(HTTPException) as caught:
            get_journey_scoped(self.journeys[0].id, self.db, self.staff)
        self.assertEqual(caught.exception.status_code, 404)
        self.patients[0].assigned_clinician_id = self.staff.id
        self.db.commit()
        self.assertEqual(scope_patient_ids(self.db, self.staff), [self.patients[0].id])
        self.assertEqual(tool_list_patients(self.db, self.staff, {})["data"]["total"], 1)
        self.assertEqual(get_journey_scoped(self.journeys[0].id, self.db, self.staff).id,
                         self.journeys[0].id)
        with self.assertRaises(HTTPException):
            get_journey_scoped(self.journeys[1].id, self.db, self.staff)
        self.patients[0].assigned_clinician_id = None
        self.db.commit()
        with self.assertRaises(HTTPException):
            get_journey_scoped(self.journeys[0].id, self.db, self.staff)

    def test_tool_arguments_cannot_add_arbitrary_fields_or_unassigned_journey(self):
        spec = get_spec("get_journey_steps")
        with self.assertRaises(ToolValidationError):
            prepare_arguments(self.db, self.staff, spec,
                              {"journey_id": str(self.journeys[0].id), "sql": "SELECT * FROM users"})
        with self.assertRaises(HTTPException) as caught:
            execute_tool(self.db, self.staff, "get_journey_steps",
                         {"journey_id": str(self.journeys[0].id)})
        self.assertEqual(caught.exception.status_code, 404)

    def test_public_signup_route_is_removed(self):
        self.assertNotIn("/auth/signup", {route.path for route in auth_router.routes})

    def test_patient_account_cannot_be_promoted_to_staff(self):
        now = datetime.now(timezone.utc)
        patient_user = User(id=uuid4(), email="patient@test.test", password_hash="x",
                            display_name="Patient", role="PATIENT",
                            patient_id=self.patients[0].id, is_active=True,
                            created_at=now, updated_at=now)
        self.db.add(patient_user)
        self.db.commit()
        with self.assertRaises(HTTPException) as caught:
            set_user_role(patient_user.id, RoleUpdate(role="ADMIN"), self.db, self.admin)
        self.assertEqual(caught.exception.status_code, 422)

    def test_exception_update_is_scoped_before_proposal(self):
        item = ExceptionRecord(id=uuid4(), journey_id=self.journeys[0].id,
                               severity="HIGH", exception_type="DELAY",
                               title="Delayed", description="Synthetic note",
                               status="OPEN", created_at=datetime.now(timezone.utc))
        self.db.add(item)
        self.db.commit()
        with self.assertRaises(ToolValidationError):
            prepare_arguments(self.db, self.staff, get_spec("update_exception"),
                              {"exception_id": str(item.id), "status": "RESOLVED"})

    def test_role_tools_are_filtered(self):
        patient_tools = {t["function"]["name"] for t in tools_for_llm(SimpleNamespace(role="PATIENT"))}
        self.assertNotIn("list_users", patient_tools)
        self.assertNotIn("start_pathway", patient_tools)
        self.assertTrue(all(t["function"]["parameters"]["additionalProperties"] is False
                            for t in tools_for_llm(self.staff)))

    @patch("app.api.v1.admin._audit_change")
    def test_admin_assigns_clinician_once(self, record_audit):
        patient_id = self.patients[0].id
        assign_patient(self.staff.id, patient_id, self.db, self.admin)
        self.assertEqual(scope_patient_ids(self.db, self.staff), [patient_id])
        assign_patient(self.staff.id, patient_id, self.db, self.admin)
        self.assertEqual(scope_patient_ids(self.db, self.staff), [patient_id])
        with self.assertRaises(HTTPException) as caught:
            unassign_patient(self.staff.id, patient_id, self.db, self.admin)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual([call.args[2] for call in record_audit.call_args_list],
                         ["assign_patient"])


class ConfirmationBindingTest(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=uuid4(), role="ADMIN")
        self.session = SimpleNamespace(id=uuid4())
        self.patient_id = uuid4()
        self.message = SimpleNamespace(id=uuid4(), role="assistant", session_id=self.session.id)
        self.pending = {
            "name": "start_pathway", "arguments": {"patient_id": str(self.patient_id),
                                                     "pathway_id": str(uuid4())},
            "user_id": str(self.user.id), "patient_id": str(self.patient_id),
            "correlation_id": str(uuid4()), "nonce": str(uuid4()),
            "status": "pending",
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            "description": {"title": "Start pathway"},
        }
        self.pending["binding"] = sign_pending_action(self.pending, self.user.id, self.session.id)
        self.message.meta = {"pending_action": self.pending}
        self.db = Mock()
        self.db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = self.message

    def test_signature_covers_action_user_session_patient_and_parameters(self):
        self.assertTrue(verify_pending_action(self.pending, self.user.id, self.session.id))
        self.assertFalse(verify_pending_action(self.pending, uuid4(), self.session.id))
        self.assertFalse(verify_pending_action(self.pending, self.user.id, uuid4()))
        for field, value in (("name", "create_pathway"), ("patient_id", str(uuid4())),
                             ("arguments", {"patient_id": str(uuid4())})):
            changed = dict(self.pending, **{field: value})
            self.assertFalse(verify_pending_action(changed, self.user.id, self.session.id))

    def test_audit_omits_free_text_and_records_trace_metadata(self):
        args = {"patient_id": str(self.patient_id), "comment": "private clinical details"}
        audit(self.db, user=self.user, session=self.session,
              tool_name="submit_event", event="proposed", parameters=args,
              correlation_id=uuid4())
        row = self.db.add.call_args.args[0]
        self.assertEqual(row.patient_id, self.patient_id)
        self.assertEqual(row.role_at_time, "ADMIN")
        self.assertEqual(row.parameters["fields"], ["comment", "patient_id"])
        self.assertNotIn("private clinical details", str(row.parameters))

    @patch("app.services.chat_service.get_session_for_user")
    @patch("app.services.chat_service.chat_tools.execute_tool")
    def test_tampered_confirmation_does_not_execute(self, execute, get_session):
        get_session.return_value = self.session
        self.pending["arguments"]["patient_id"] = str(uuid4())
        with self.assertRaises(HTTPException) as caught:
            confirm_action(self.db, self.user, self.session.id, self.message.id)
        self.assertEqual(caught.exception.status_code, 422)
        execute.assert_not_called()

    @patch("app.services.chat_service.get_session_for_user")
    @patch("app.services.chat_service.chat_tools.execute_tool")
    @patch("app.services.chat_service.audit")
    @patch("app.services.chat_service._add_message")
    @patch("app.services.chat_service._set_pending_status")
    def test_expired_confirmation_does_not_execute(self, set_status, add_message,
                                                    audit, execute, get_session):
        get_session.return_value = self.session
        self.pending["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        self.pending["binding"] = sign_pending_action(self.pending, self.user.id, self.session.id)
        add_message.return_value = SimpleNamespace(id=uuid4())
        confirm_action(self.db, self.user, self.session.id, self.message.id)
        execute.assert_not_called()
        self.assertEqual(set_status.call_args.args[2], "expired")

    @patch("app.services.chat_service.get_session_for_user")
    @patch("app.services.chat_service.chat_tools.execute_tool")
    @patch("app.services.chat_service.chat_tools.prepare_arguments")
    @patch("app.services.chat_service.audit")
    @patch("app.services.chat_service._add_message")
    @patch("app.services.chat_service._set_pending_status")
    def test_revalidation_failure_prevents_execution(self, set_status, add_message,
                                                     audit, prepare, execute, get_session):
        get_session.return_value = self.session
        prepare.side_effect = ToolValidationError("Patient no longer assigned")
        add_message.return_value = SimpleNamespace(id=uuid4())
        confirm_action(self.db, self.user, self.session.id, self.message.id)
        execute.assert_not_called()
        self.assertEqual(set_status.call_args.args[2], "failed")


if __name__ == "__main__":
    unittest.main()
