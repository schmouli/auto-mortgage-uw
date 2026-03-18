class DocumentManagementError(Exception):
    """Base exception for document management module."""
    pass


class DocumentNotFoundError(DocumentManagementError):
    """Raised when a document is not found."""
    pass


class DocumentUploadError(DocumentManagementError):
    """Raised when document upload fails."""
    pass


class InvalidFileTypeError(DocumentManagementError):
    """Raised when an unsupported file type is provided."""
    pass


class FileSizeExceededError(DocumentManagementError):
    """Raised when file exceeds maximum allowed size."""
    pass