from mortgage_underwriting.common.exceptions import AppException


class OrchestratorException(AppException):
    """Base exception for Orchestrator Service."""
    pass


class ApplicationNotFoundException(OrchestratorException):
    """Raised when an application is not found."""
    def __init__(self, application_id: str):
        super().__init__(f"Application {application_id} not found")


class DocumentUploadException(OrchestratorException):
    """Raised when document upload fails."""
    def __init__(self, message: str):
        super().__init__(f"Document upload failed: {message}")


class InvalidBorrowerDataException(OrchestratorException):
    """Raised when borrower data is invalid."""
    def __init__(self, message: str):
        super().__init__(f"Invalid borrower data: {message}")