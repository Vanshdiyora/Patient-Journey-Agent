import uuid
class MockSchedulingService:
    def request_appointment(self, payload):
        return {"accepted": True, "status": "REQUEST_CREATED", "external_reference": f"MOCK-APT-{uuid.uuid4().hex[:10]}", "payload": payload}
    def reschedule_appointment(self, payload):
        return {"accepted": True, "status": "RESCHEDULE_REQUEST_CREATED", "external_reference": f"MOCK-RES-{uuid.uuid4().hex[:10]}", "payload": payload}
