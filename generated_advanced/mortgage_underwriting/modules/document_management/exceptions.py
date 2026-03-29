class DocumentManagementError(Exception):
    """Base exception for document management module."""
    pass


class DocumentNotFoundError(DocumentManagementError):
    """Raised when a document is not found."""
    pass


class DocumentUploadError(DocumentManagementError):
    """Raised when document upload fails."""
    pass


class DocumentVerificationError(DocumentManagementError):
    """Raised when document verification fails."""
    pass