from mortgage_underwriting.common.exceptions import AppException


class DPTException(AppException):
    """Base exception for Document Processing Transformer module."""
    pass


class DPTApplicationNotFoundError(DPTException):
    """Raised when referenced application does not exist."""
    def __init__(self, application_id: str):
        self.application_id = application_id
        super().__init__(f"Application {application_id} not found")


class DPTInvalidDocumentTypeError(DPTException):
    """Raised when document type is not supported."""
    def __init__(self, document_type: str):
        self.document_type = document_type
        super().__init__(f"Invalid document type: {document_type}")