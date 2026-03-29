from mortgage_underwriting.common.exceptions import AppException

class AuthException(AppException):
    """Base authentication exception."""
    pass

class InvalidCredentials(AuthException):
    """Raised when provided credentials are invalid."""
    def __init__(self) -> None:
        super().__init__(
            detail="Invalid email or password",
            error_code="INVALID_CREDENTIALS"
        )

class UserAlreadyExists(AuthException):
    """Raised when attempting to register with an existing email."""
    def __init__(self) -> None:
        super().__init__(
            detail="A user with this email already exists",
            error_code="USER_EXISTS"
        )

class WeakPassword(AuthException):
    """Raised when password does not meet security requirements."""
    def __init__(self) -> None:
        super().__init__(
            detail="Password must be at least 10 characters and contain uppercase, number, and special character",
            error_code="WEAK_PASSWORD"
        )

class RefreshTokenExpired(AuthException):
    """Raised when refresh token is expired or invalid."""
    def __init__(self) -> None:
        super().__init__(
            detail="Refresh token is invalid or expired",
            error_code="REFRESH_TOKEN_EXPIRED"
        )

class UserNotFound(AuthException):
    """Raised when user is not found."""
    def __init__(self) -> None:
        super().__init__(
            detail="User not found",
            error_code="USER_NOT_FOUND"
        )