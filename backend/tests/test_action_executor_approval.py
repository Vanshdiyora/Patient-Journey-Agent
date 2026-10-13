"""Approval-policy checks for agent-executed actions."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from app.action_registry.definitions import ActionDefinition
from app.models import ActionExecution, Journey
from app.orchestration.action_executor import ActionExecutor


class ActionExecutorApprovalTest(unittest.TestCase):
    def make_db(self):
        db = Mock()

        def query(model):
            query_result = Mock()
            if model is ActionExecution:
                query_result.filter.return_value.first.return_value = None
            elif model is Journey:
                query_result.filter.return_value.first.return_value = SimpleNamespace(priority="MEDIUM")
            else:
                raise AssertionError(f"Unexpected query: {model}")
            return query_result

        db.query.side_effect = query
        return db

    def execute(self, allow_agent_self_approval, requested_by="SUPERVISOR"):
        db = self.make_db()
        with patch("app.orchestration.action_executor.settings", SimpleNamespace(email_enabled=False)):
            execution, meta = ActionExecutor(db).execute(
                uuid4(),
                uuid4(),
                "CREATE_COORDINATOR_TASK",
                {"step_name": "Follow-up", "reason": "Needs coordinator review"},
                requested_by=requested_by,
                allow_agent_self_approval=allow_agent_self_approval,
            )
        return db, execution, meta

    def test_agent_can_self_approve_only_the_allowlisted_task_action(self):
        db, execution, meta = self.execute(allow_agent_self_approval=True)

        self.assertEqual(execution.status, "SUCCESS")
        self.assertTrue(meta["verified"])
        self.assertTrue(meta["auto_approved"])
        self.assertEqual(execution.response_payload["approval"]["decision"], "AUTO_APPROVED")
        self.assertEqual(execution.response_payload["approval"]["by_role"], "AGENT")
        self.assertTrue(any(isinstance(call.args[0], ActionExecution) for call in db.add.call_args_list))

    def test_gated_action_still_waits_for_staff_without_agent_approval_permission(self):
        db = self.make_db()
        executor = ActionExecutor(db)
        executor.registry.validate = Mock(return_value=ActionDefinition(
            "FUTURE_GATED_ACTION", "A future gated action", True, "not_configured",
        ))

        execution, meta = executor.execute(
            uuid4(), uuid4(), "FUTURE_GATED_ACTION", {}, allow_agent_self_approval=True,
        )

        self.assertEqual(execution.status, "REQUESTED")
        self.assertTrue(meta["awaiting_approval"])
        self.assertFalse(meta["verified"])

    def test_task_action_still_requires_staff_approval_without_agent_opt_in(self):
        _, execution, meta = self.execute(allow_agent_self_approval=False)

        self.assertEqual(execution.status, "REQUESTED")
        self.assertTrue(meta["awaiting_approval"])
        self.assertFalse(meta["verified"])

    def test_non_agent_cannot_use_agent_self_approval(self):
        _, execution, meta = self.execute(
            allow_agent_self_approval=True,
            requested_by="HUMAN",
        )

        self.assertEqual(execution.status, "REQUESTED")
        self.assertTrue(meta["awaiting_approval"])
        self.assertFalse(meta["verified"])


if __name__ == "__main__":
    unittest.main()
