class FintracComplianceError(Exception):
    """Base exception for FINTRAC compliance module."""
    def __init__(self, detail: str, error_code: str):
        self.detail = detail
        self.error_code = error_code
        super().__init__(detail)


class VerificationAlreadyExistsError(FintracComplianceError):
    """Raised when trying to create a verification that already exists."""
    pass


class ApplicationNotFoundError(FintracComplianceError):
    """Raised when an application is not found."""
    pass


class ClientNotInApplicationError(FintracComplianceError):
    """Raised when a client is not part of the specified application."""
    pass


class InvalidIdExpiryDateError(FintracComplianceError):
    """Raised when ID expiry date is invalid (e.g., in the past)."""
    pass