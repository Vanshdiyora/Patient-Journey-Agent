import uuid
class MockClinicalEventService:
    def create_event(self, payload):
        return {"accepted": True, "status": "EVENT_CREATED", "external_reference": f"MOCK-EVT-{uuid.uuid4().hex[:10]}", "payload": payload}
