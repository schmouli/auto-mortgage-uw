from mortgage_underwriting.common.exceptions import AppException


class FintracError(AppException):
    """Base exception for FINTRAC compliance module."""
    pass


class VerificationAlreadyExistsError(FintracError):
    """Raised when attempting to create a duplicate verification."""
    def __init__(self, detail: str = "Verification already exists for client", error_code: str = "FINTRAC_003"):
        super().__init__(detail=detail, error_code=error_code)


class InvalidIdExpiryError(FintracError):
    """Raised when ID expiry date is invalid."""
    def __init__(self, detail: str = "ID expiry date must be in the future", error_code: str = "FINTRAC_004"):
        super().__init__(detail=detail, error_code=error_code)


class InvalidVerificationMethodError(FintracError):
    """Raised when verification method or ID type is invalid."""
    def __init__(self, detail: str = "Invalid verification method or ID type", error_code: str = "FINTRAC_005"):
        super().__init__(detail=detail, error_code=error_code)


class InsufficientPermissionsError(FintracError):
    """Raised when user lacks required permissions."""
    def __init__(self, detail: str = "Insufficient permissions", error_code: str = "FINTRAC_008"):
        super().__init__(detail=detail, error_code=error_code)