from mortgage_underwriting.common.exceptions import AppException


class DecisionNotFoundError(AppException):
    """Raised when a decision record cannot be found."""
    pass


class DecisionEvaluationError(AppException):
    """Raised when there's an error during decision evaluation."""
    pass