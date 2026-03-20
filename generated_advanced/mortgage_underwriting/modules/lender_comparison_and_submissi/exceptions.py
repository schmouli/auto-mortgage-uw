from mortgage_underwriting.common.exceptions import AppException


class LenderNotFoundError(AppException):
    """Raised when a requested lender is not found."""
    pass


class LenderProductNotFoundError(AppException):
    """Raised when a requested lender product is not found."""
    pass


class InvalidLenderTypeError(AppException):
    """Raised when an invalid lender type is provided."""
    pass


class InvalidMortgageTypeError(AppException):
    """Raised when an invalid mortgage type is provided."""
    pass


class SubmissionCreationError(AppException):
    """Raised when there's an error creating a lender submission."""
    pass


class SubmissionUpdateError(AppException):
    """Raised when there's an error updating a lender submission."""
    pass


class LenderMatchingError(AppException):
    """Raised when there's an error during lender matching process."""
    pass