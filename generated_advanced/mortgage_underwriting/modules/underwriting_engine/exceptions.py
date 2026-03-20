from mortgage_underwriting.common.exceptions import AppException

class UnderwritingCalculationError(AppException):
    pass

class UnderwritingNotFoundError(AppException):
    pass

class UnderwritingOverrideError(AppException):
    pass