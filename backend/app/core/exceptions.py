class OrchestrationError(Exception):
    pass

class ActionNotAllowedError(OrchestrationError):
    pass

class VerificationError(OrchestrationError):
    pass
