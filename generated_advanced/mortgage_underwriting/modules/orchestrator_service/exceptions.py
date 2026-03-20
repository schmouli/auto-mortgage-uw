from mortgage_underwriting.common.exceptions import AppException


class OrchestratorException(AppException):
    """Base exception for Orchestrator Service."""
    pass


class DuplicateApplicationException(OrchestratorException):
    """Raised when trying to submit an application for a borrower with an active application."""
    def __init__(self):
        super().__init__(
            detail="Borrower already has an active application",
            error_code="ORCHESTRATOR_003"
        )


class InvalidDocumentException(OrchestratorException):
    """Raised when document validation fails."""
    def __init__(self, message: str = "Invalid document provided"):
        super().__init__(
            detail=message,
            error_code="ORCHESTRATOR_002"
        )


class ApplicationNotFoundException(OrchestratorException):
    """Raised when application is not found."""
    def __init__(self):
        super().__init__(
            detail="Application not found",
            error_code="ORCHESTRATOR_006"
        )


class FintracVerificationNotFoundException(OrchestratorException):
    """Raised when FINTRAC verification record is not found."""
    def __init__(self):
        super().__init__(
            detail="FINTRAC verification not found",
            error_code="ORCHESTRATOR_008"
        )