from mortgage_underwriting.common.exceptions import AppException

class DeploymentException(AppException):
    """Base exception for deployment module."""
    pass

class DeploymentNotFoundError(DeploymentException):
    """Raised when a deployment is not found."""
    pass