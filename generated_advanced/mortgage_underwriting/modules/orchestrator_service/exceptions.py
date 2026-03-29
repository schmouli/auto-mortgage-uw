from mortgage_underwriting.common.exceptions import AppException


class OrchestratorException(AppException):
    """Base exception for orchestrator service."""
    pass


class InvalidApplicationData(OrchestratorException):
    """Raised when application data fails validation."""
    pass


class DocumentProcessingError(OrchestratorException):
    """Raised when document processing fails."""
    pass


class PolicyEvaluationError(OrchestratorException):
    """Raised when policy evaluation encounters an error."""
    pass


class DecisionEngineError(OrchestratorException):
    """Raised when decision engine fails to produce a result."""
    pass