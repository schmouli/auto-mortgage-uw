from mortgage_underwriting.common.exceptions import AppException


class ClientIntakeException(AppException):
    """Base exception for client intake module."""
    pass


class ClientNotFoundError(ClientIntakeException):
    """Raised when a client is not found."""
    pass


class ApplicationNotFoundError(ClientIntakeException):
    """Raised when an application is not found."""
    pass


class InvalidApplicationStatusError(ClientIntakeException):
    """Raised when trying to perform an invalid operation on an application based on its status."""
    pass


class CoBorrowerCreationError(ClientIntakeException):
    """Raised when there's an error creating a co-borrower."""
    pass