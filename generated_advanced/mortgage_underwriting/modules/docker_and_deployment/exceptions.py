class DeploymentException(Exception):
    """Base exception for deployment module."""
    pass

class HealthCheckCreationError(DeploymentException):
    """Raised when health check creation fails."""
    pass

class DependencyHealthRetrievalError(DeploymentException):
    """Raised when dependency health retrieval fails."""
    pass