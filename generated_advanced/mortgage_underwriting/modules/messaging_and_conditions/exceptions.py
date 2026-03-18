from mortgage_underwriting.common.exceptions import AppException


class MessagingConditionsException(AppException):
    """Base exception for messaging and conditions module."""
    pass


class MessageNotFoundError(MessagingConditionsException):
    """Raised when a requested message is not found."""
    error_code = "MSG_001"


class UnauthorizedMessageAccessException(MessagingConditionsException):
    """Raised when user tries to access a message they're not part of."""
    error_code = "MSG_002"


class InvalidRecipientException(MessagingConditionsException):
    """Raised when trying to send a message to non-participant."""
    error_code = "MSG_004"


class ConditionNotFoundError(MessagingConditionsException):
    """Raised when a requested condition is not found."""
    error_code = "COND_001"


class UnauthorizedConditionAccessException(MessagingConditionsException):
    """Raised when user tries to access a condition outside their scope."""
    error_code = "COND_002"