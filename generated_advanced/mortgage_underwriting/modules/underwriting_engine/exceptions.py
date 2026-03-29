from mortgage_underwriting.common.exceptions import AppException


class UnderwritingCalculationError(AppException):
    """Raised when underwriting calculation fails."""
    pass


class UnderwritingEvaluationError(AppException):
    """Raised when underwriting evaluation fails."""
    pass


class UnderwritingResultNotFoundError(AppException):
    """Raised when underwriting result is not found."""
    pass


class UnderwritingOverrideError(AppException):
    """Raised when underwriting override operation fails."""
    pass