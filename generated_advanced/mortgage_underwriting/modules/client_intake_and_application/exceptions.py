from mortgage_underwriting.common.exceptions import AppException


class ClientIntakeError(AppException):
    """Base exception for client intake module."""
    pass


class InvalidSINError(ClientIntakeError):
    """Raised when SIN validation fails."""
    pass


class ApplicationNotDraftError(ClientIntakeError):
    """Raised when trying to submit a non-draft application."""
    pass


class ApplicationValidationError(ClientIntakeError):
    """Raised when application data fails validation."""
    pass