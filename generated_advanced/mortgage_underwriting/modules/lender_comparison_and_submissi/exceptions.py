from mortgage_underwriting.common.exceptions import AppException


class LenderNotFoundError(AppException):
    """Raised when a lender is not found."""
    pass


class ProductNotFoundError(AppException):
    """Raised when a lender product is not found."""
    pass


class SubmissionNotFoundError(AppException):
    """Raised when a lender submission is not found."""
    pass


class MatchingCriteriaInvalidError(AppException):
    """Raised when lender matching criteria are invalid."""
    pass