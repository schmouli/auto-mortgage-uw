class FintracComplianceError(Exception):
    """Base exception for FINTRAC compliance module."""
    def __init__(self, detail: str, error_code: str):
        self.detail = detail
        self.error_code = error_code
        super().__init__(detail)


class VerificationAlreadyExistsError(FintracComplianceError):
    """Raised when attempting to create a duplicate verification."""
    def __init__(self, detail: str = "Verification already exists for this client"):
        super().__init__(detail, "FINTRAC_003")


class InvalidProvinceCodeError(FintracComplianceError):
    """Raised when an invalid province code is provided."""
    def __init__(self, detail: str = "Invalid province code provided"):
        super().__init__(detail, "FINTRAC_002")


class ExpiredIdError(FintracComplianceError):
    """Raised when an expired ID is provided."""
    def __init__(self, detail: str = "Provided ID has expired"):
        super().__init__(detail, "FINTRAC_002")


class StructuringDetectedError(FintracComplianceError):
    """Raised when potential structuring is detected."""
    def __init__(self, detail: str = "Potential structuring detected"):
        super().__init__(detail, "FINTRAC_004")