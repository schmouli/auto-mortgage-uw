```python
# Common base exception assumed to exist in project
class BaseBusinessException(Exception):
    """Base class for business logic exceptions"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class LenderNotFoundError(BaseBusinessException):
    """Raised when a requested lender cannot be found"""
    def __init__(self, message: str = "Lender not found"):
        super().__init__(message)


class ProductNotFoundError(BaseBusinessException):
    """Raised when no products are found for a lender or search criteria"""
    def __init__(self, message: str = "No matching products found"):
        super().__init__(message)


class SubmissionNotFoundError(BaseBusinessException):
    """Raised when attempting to access a non-existent submission"""
    def __init__(self, message: str = "Submission not found"):
        super().__init__(message)


class InvalidSubmissionStatusError(BaseBusinessException):
    """Raised when trying to set an invalid submission status"""
    def __init__(self, message: str = "Invalid submission status transition"):
        super().__init__(message)
```