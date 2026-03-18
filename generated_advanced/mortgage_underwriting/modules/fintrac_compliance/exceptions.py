from mortgage_underwriting.common.exceptions import AppException


class FintracError(AppException):
    """Base exception for FINTRAC compliance module."""
    pass


class VerificationNotFoundError(FintracError):
    """Raised when requested verification record does not exist."""
    def __init__(self, verification_id: int) -> None:
        super().__init__(f"Verification record {verification_id} not found")


class ReportSubmissionError(FintracError):
    """Raised when there is an error submitting a FINTRAC report."""
    def __init__(self, message: str) -> None:
        super().__init__(f"Report submission failed: {message}")


class EncryptionError(FintracError):
    """Raised when PII encryption fails."""
    def __init__(self, field_name: str) -> None:
        super().__init__(f"Failed to encrypt {field_name}")