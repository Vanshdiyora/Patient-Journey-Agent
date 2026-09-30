import uuid
class MockDocumentService:
    def request_document(self, payload):
        return {"accepted": True, "status": "REQUEST_CREATED", "external_reference": f"MOCK-DOC-{uuid.uuid4().hex[:10]}", "payload": payload}
