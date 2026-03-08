from mortgage_underwriting.common.exceptions import AppException


class ClientIntakeError(AppException):
    """Base exception for client intake operations."""
    pass


class InvalidSINError(ClientIntakeError):
    """Raised when SIN validation fails."""
    pass


class InvalidDOBError(ClientIntakeError):
    """Raised when date of birth validation fails."""
    pass


class ApplicationValidationError(ClientIntakeError):
    """Raised when application data validation fails."""
    pass


class InsuranceCalculationError(ClientIntakeError):
    """Raised when there's an error calculating insurance requirements."""
    pass


class UnauthorizedAccessError(ClientIntakeError):
    """Raised when user attempts to access unauthorized resources."""
    pass