from mortgage_underwriting.common.exceptions import AppException


class DPTServiceException(AppException):
    """Base exception for DPT service."""
    pass


class InvalidDocumentTypeException(DPTServiceException):
    """Raised when an invalid document type is provided."""
    pass


class S3KeyValidationException(DPTServiceException):
    """Raised when S3 key validation fails."""
    pass


class ExtractionProcessingException(DPTServiceException):
    """Raised when there's an error during extraction processing."""
    pass