from mortgage_underwriting.common.exceptions import AppException


class DocumentManagementError(AppException):
    """Base exception for document management module."""
    pass


class DocumentNotFoundError(DocumentManagementError):
    """Raised when a document is not found."""
    pass


class DocumentValidationError(DocumentManagementError):
    """Raised when document validation fails."""
    pass


class DocumentUploadError(DocumentManagementError):
    """Raised when document upload fails."""
    pass