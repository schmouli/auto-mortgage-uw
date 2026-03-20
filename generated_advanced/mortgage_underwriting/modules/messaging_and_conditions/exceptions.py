from mortgage_underwriting.common.exceptions import AppException

class MessagingException(AppException):
    """Base exception for messaging operations."""
    pass

class ConditionException(AppException):
    """Base exception for condition operations."""
    pass