from mortgage_underwriting.common.exceptions import AppException


class DPTBaseException(AppException):
    """Base exception for Document Processing Transformer module."""
    pass


class DPTInvalidInputError(DPTBaseException):
    """Raised when input validation fails."""
    pass


class DPTDocumentAlreadySubmittedError(DPTBaseException):
    """Raised when attempting to submit a duplicate document."""
    pass


class DPTJobNotFoundError(DPTBaseException):
    """Raised when requested job does not exist."""
    pass