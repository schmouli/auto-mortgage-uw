class PolicyException(Exception):
    """Base exception for XML Policy Service."""
    pass


class PolicyNotFoundException(PolicyException):
    """Raised when a requested policy is not found."""
    pass


class PolicyValidationError(PolicyException):
    """Raised when there is an issue validating policy XML or data."""
    pass