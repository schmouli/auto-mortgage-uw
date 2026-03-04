```python
from app.exceptions.base import BaseCustomException


class UserAlreadyExistsError(BaseCustomException):
    """Raised when trying to register a user with an email that already exists."""
    def __init__(self, message: str = "User with this email already exists"):
        self.message = message
        super().__init__(self.message)


class InvalidCredentialsError(BaseCustomException):
    """Raised when provided credentials are invalid during authentication."""
    def __init__(self, message: str = "Invalid credentials provided"):
        self.message = message
        super().__init__(self.message)


class UserInactiveError(BaseCustomException):
    """Raised when trying to authenticate an inactive user."""
    def __init__(self, message: str = "User account is inactive"):
        self.message = message
        super().__init__(self.message)


class RefreshTokenInvalidError(BaseCustomException):
    """Raised when refresh token is invalid, expired, or not found."""
    def __init__(self, message: str = "Refresh token is invalid or expired"):
        self.message = message
        super().__init__(self.message)
```