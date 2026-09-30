from app.core.exceptions import VerificationError

class VerificationLayer:
    def verify(self, action_type: str, response: dict):
        if not response or response.get("accepted") is not True:
            raise VerificationError(response.get("reason", "External action was not accepted") if response else "Empty external response")
        return {"verified": True, "status": response.get("status", "UNKNOWN"), "external_reference": response.get("external_reference")}
