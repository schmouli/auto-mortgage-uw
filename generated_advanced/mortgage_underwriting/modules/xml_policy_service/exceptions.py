from mortgage_underwriting.common.exceptions import AppException

class PolicyNotFoundError(AppException):
    """Raised when a requested policy cannot be found."""
    pass

class InvalidPolicyXMLError(AppException):
    """Raised when policy XML content is invalid or malformed."""
    pass