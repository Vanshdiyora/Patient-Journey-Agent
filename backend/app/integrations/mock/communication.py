import uuid
class MockCommunicationService:
    def send_reminder(self, payload):
        return {"accepted": True, "status": "MESSAGE_SENT", "external_reference": f"MOCK-MSG-{uuid.uuid4().hex[:10]}", "payload": payload}
