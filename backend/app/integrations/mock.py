"""Local service adapters used when external integrations are not configured."""

import uuid

class MockSchedulingService:
    def request_appointment(self, payload):
        return {"accepted": True, "status": "REQUEST_CREATED", "external_reference": f"MOCK-APT-{uuid.uuid4().hex[:10]}", "payload": payload}
    def reschedule_appointment(self, payload):
        return {"accepted": True, "status": "RESCHEDULE_REQUEST_CREATED", "external_reference": f"MOCK-RES-{uuid.uuid4().hex[:10]}", "payload": payload}

class MockCommunicationService:
    def send_reminder(self, payload):
        return {"accepted": True, "status": "MESSAGE_SENT", "external_reference": f"MOCK-MSG-{uuid.uuid4().hex[:10]}", "payload": payload}

class MockDocumentService:
    def request_document(self, payload):
        return {"accepted": True, "status": "REQUEST_CREATED", "external_reference": f"MOCK-DOC-{uuid.uuid4().hex[:10]}", "payload": payload}

class MockClinicalEventService:
    def create_event(self, payload):
        return {"accepted": True, "status": "EVENT_CREATED", "external_reference": f"MOCK-EVT-{uuid.uuid4().hex[:10]}", "payload": payload}
