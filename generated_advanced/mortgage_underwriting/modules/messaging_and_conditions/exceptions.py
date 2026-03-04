```python
from ..common.exceptions import OnLendBaseException


class MessageNotFoundError(OnLendBaseException):
    """Raised when a requested message cannot be found"""
    def __init__(self, message: str = "Message not found"):
        self.message = message
        super().__init__(self.message)


class ConditionNotFoundError(OnLendBaseException):
    """Raised when a requested condition cannot be found"""
    def __init__(self, message: str = "Condition not found"):
        self.message = message
        super().__init__(self.message)


class UnauthorizedAccessError(OnLendBaseException):
    """Raised when user attempts to access unauthorized resources"""
    def __init__(self, message: str = "Unauthorized access"):
        self.message = message
        super().__init__(self.message)
```