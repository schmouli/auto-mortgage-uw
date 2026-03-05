class UserAlreadyExistsError(Exception):
    """Raised when trying to register a user with an email that already exists"""
    pass

class InvalidCredentialsError(Exception):
    """Raised when login credentials are invalid"""
    pass

class UserInactiveError(Exception):
    """Raised when trying to authenticate an inactive user"""
    pass

class RefreshTokenInvalidError(Exception):
    """Raised when refresh token is invalid or expired"""
    pass
```