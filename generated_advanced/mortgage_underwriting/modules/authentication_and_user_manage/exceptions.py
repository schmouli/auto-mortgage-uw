from mortgage_underwriting.common.exceptions import AppException


class InvalidCredentialsError(AppException):
    pass


class UserAlreadyExistsError(AppException):
    pass


class InvalidRefreshTokenError(AppException):
    pass


class UserNotFoundError(AppException):
    pass