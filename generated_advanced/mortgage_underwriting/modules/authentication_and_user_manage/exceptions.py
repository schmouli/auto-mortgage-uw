--- exceptions.py ---
from mortgage_underwriting.common.exceptions import AppException

class AuthException(AppException):
    pass

class UserNotFoundException(AuthException):
    pass