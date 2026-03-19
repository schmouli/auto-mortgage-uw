from mortgage_underwriting.common.exceptions import AppException


class UnderwritingError(AppException):
    """Base exception for underwriting module."""
    pass


class CalculationError(UnderwritingError):
    """Raised when underwriting calculations fail."""
    pass


class EvaluationError(UnderwritingError):
    """Raised when application evaluation fails."""
    pass


class OverrideError(UnderwritingError):
    """Raised when override creation fails."""
    pass


class ValidationError(UnderwritingError):
    """Raised when validation fails."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)