class DPTServiceException(Exception):
    """Base exception for Document Processing Transformer service"""
    pass


class DocumentProcessingFailedException(DPTServiceException):
    """Raised when document processing fails"""
    pass


class ExtractionNotFoundException(DPTServiceException):
    """Raised when trying to access a non-existent extraction job"""
    pass
```