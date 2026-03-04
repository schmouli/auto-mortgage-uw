```python
class DPTBaseException(Exception):
    """Base exception class for DPT Service"""
    pass


class DPTServiceException(DPTBaseException):
    """General service-level exception"""
    def __init__(self, message: str):
        super().__init__(message)


class ExtractionNotFoundException(DPTBaseException):
    """Raised when an extraction job cannot be found"""
    def __init__(self, message: str):
        super().__init__(message)


class DocumentProcessingFailedException(DPTBaseException):
    """Raised when document processing fails due to internal issues"""
    def __init__(self, message: str):
        super().__init__(message)
```