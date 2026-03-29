class MessagingConditionsException(Exception):
    """Base exception for messaging and conditions module."""
    def __init__(self, detail: str, error_code: str):
        self.detail = detail
        self.error_code = error_code
        super().__init__(detail)


class MessageNotFoundError(MessagingConditionsException):
    """Raised when a requested message cannot be found."""
    def __init__(self, detail: str = "Message not found", error_code: str = "MESSAGING_001"):
        super().__init__(detail, error_code)


class ConditionNotFoundError(MessagingConditionsException):
    """Raised when a requested condition cannot be found."""
    def __init__(self, detail: str = "Condition not found", error_code: str = "CONDITION_001"):
        super().__init__(detail, error_code)


class InvalidConditionStatusError(MessagingConditionsException):
    """Raised when attempting to set an invalid condition status."""
    def __init__(self, detail: str = "Invalid condition status", error_code: str = "CONDITION_002"):
        super().__init__(detail, error_code)


class UnauthorizedMessageAccessError(MessagingConditionsException):
    """Raised when user attempts to access message they're not authorized for."""
    def __init__(self, detail: str = "Not authorized to access this message", error_code: str = "MESSAGING_004"):
        super().__init__(detail, error_code)


class UnauthorizedConditionAccessError(MessagingConditionsException):
    """Raised when user attempts to access condition they're not authorized for."""
    def __init__(self, detail: str = "Not authorized to access this condition", error_code: str = "CONDITION_004"):
        super().__init__(detail, error_code)