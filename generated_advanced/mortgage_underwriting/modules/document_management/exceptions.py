from mortgage_underwriting.common.exceptions import AppException

class DocumentManagementError(AppException):
    """Base exception for document management module."""
    pass

class DocumentNotFoundError(DocumentManagementError):
    """Raised when a requested document cannot be found."""
    error_code = "DOC_NOT_FOUND"
    status_code = 404

class DocumentValidationError(DocumentManagementError):
    """Raised when document validation fails."""
    error_code = "DOC_VALIDATION_ERROR"
    status_code = 400

class DocumentUploadError(DocumentManagementError):
    """Raised when document upload fails."""
    error_code = "DOC_UPLOAD_ERROR"
    status_code = 500