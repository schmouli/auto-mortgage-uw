from mortgage_underwriting.common.exceptions import AppException

class DPTException(AppException):
    """Base exception for Document Processing Transformer service."""
    pass

class InvalidDocumentTypeError(DPTException):
    """Raised when an unsupported document type is provided."""
    error_code = "INVALID_DOCUMENT_TYPE"
    status_code = 400

class ExtractionProcessingError(DPTException):
    """Raised when there's an error during document extraction."""
    error_code = "EXTRACTION_PROCESSING_ERROR"
    status_code = 500

class JobNotFoundError(DPTException):
    """Raised when a requested extraction job cannot be found."""
    error_code = "JOB_NOT_FOUND"
    status_code = 404