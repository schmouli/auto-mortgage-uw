from mortgage_underwriting.common.exceptions import AppException

class DeploymentException(AppException):
    """Base exception for deployment module."""
    pass

class HealthCheckError(DeploymentException):
    """Raised when health check operations fail."""
    pass

class ServiceRestartError(DeploymentException):
    """Raised when service restart operations fail."""
    pass

class DeploymentLogError(DeploymentException):
    """Raised when deployment logging operations fail."""
    pass