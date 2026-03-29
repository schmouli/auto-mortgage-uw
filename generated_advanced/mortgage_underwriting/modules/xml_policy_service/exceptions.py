from mortgage_underwriting.common.exceptions import AppException


class PolicyException(AppException):
    """Base exception for policy-related errors."""
    pass


class PolicyNotFoundError(PolicyException):
    """Raised when a requested policy is not found."""
    pass


class InvalidXMLFormatError(PolicyException):
    """Raised when provided XML content is invalid or malformed."""
    pass