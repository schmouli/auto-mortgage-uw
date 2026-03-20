from mortgage_underwriting.common.exceptions import AppException


class PolicyServiceError(AppException):
    """Base exception for policy service errors."""
    pass


class PolicyNotFoundError(PolicyServiceError):
    """Raised when requested policy does not exist."""
    pass


class PolicyParsingError(PolicyServiceError):
    """Raised when policy XML cannot be parsed."""
    pass


class PolicyEvaluationError(PolicyServiceError):
    """Raised during policy evaluation process."""
    pass