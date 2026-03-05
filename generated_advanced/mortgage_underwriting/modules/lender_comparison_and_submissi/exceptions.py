from mortgage_underwriting.common.exceptions import AppException


class LenderNotFoundError(AppException):
    """Raised when a requested lender cannot be found."""
    pass


class ProductNotFoundError(AppException):
    """Raised when lender products cannot be found."""
    pass


class SubmissionNotFoundError(AppException):
    """Raised when a lender submission cannot be found."""
    pass


class InvalidSubmissionStatusError(AppException):
    """Raised when attempting an invalid status transition for a submission."""
    pass
```