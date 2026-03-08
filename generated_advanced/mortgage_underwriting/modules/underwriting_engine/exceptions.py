from mortgage_underwriting.common.exceptions import AppException


class UnderwritingCalculationError(AppException):
    """Raised when there's an error during underwriting calculation."""
    pass


class InvalidInputError(AppException):
    """Raised when input data fails validation."""
    pass


class ResultNotFoundError(AppException):
    """Raised when an underwriting result cannot be found."""
    pass


class UnauthorizedOverrideError(AppException):
    """Raised when a user attempts to perform an unauthorized override."""
    pass