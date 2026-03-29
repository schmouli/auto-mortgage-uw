from mortgage_underwriting.common.exceptions import AppException


class MigrationError(AppException):
    pass


class MigrationNotFoundError(MigrationError):
    pass


class MigrationConflictError(MigrationError):
    pass