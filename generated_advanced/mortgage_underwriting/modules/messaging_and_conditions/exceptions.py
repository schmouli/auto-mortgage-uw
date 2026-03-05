class MessagingConditionsBaseException(Exception):
    """Base exception for messaging and conditions module"""
    pass


class MessageNotFoundError(MessagingConditionsBaseException):
    """Raised when a message is not found"""
    pass


class ConditionNotFoundError(MessagingConditionsBaseException):
    """Raised when a condition is not found"""
    pass


class UnauthorizedAccessError(MessagingConditionsBaseException):
    """Raised when a user tries to access unauthorized resources"""
    pass
```