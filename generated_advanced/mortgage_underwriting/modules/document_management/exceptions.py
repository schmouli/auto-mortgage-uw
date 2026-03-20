from mortgage_underwriting.common.exceptions import AppException


class DocumentNotFoundError(AppException):
    """Raised when a requested document is not found."""
    pass


class DocumentValidationError(AppException):
    """Raised when document validation fails."""
    pass


class DocumentStorageError(AppException):
    """Raised when there's an error storing or retrieving a document."""
    pass


class DocumentSecurityError(AppException):
    """Raised when there's a security violation related to documents."""
    pass


class DocumentAuthorizationError(AppException):
    """Raised when user is not authorized to access documents."""
    pass