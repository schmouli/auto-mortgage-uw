class DocumentManagementException(Exception):
    """Base exception for Document Management module."""
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class DocumentNotFoundError(DocumentManagementException):
    """Raised when a requested document is not found."""
    def __init__(self, document_id: int):
        super().__init__(f"Document {document_id} not found", "DOC_012")


class InvalidDocumentTypeError(DocumentManagementException):
    """Raised when an invalid document type is provided."""
    def __init__(self, document_type: str):
        super().__init__(f"Invalid document type: {document_type}", "DOC_013")


class DocumentUploadFailedException(DocumentManagementException):
    """Raised when document upload fails."""
    def __init__(self, reason: str):
        super().__init__(f"Document upload failed: {reason}", "DOC_014")


class DocumentVerificationException(DocumentManagementException):
    """Raised when document verification process fails."""
    def __init__(self, document_id: int, reason: str):
        super().__init__(f"Document {document_id} verification failed: {reason}", "DOC_015")