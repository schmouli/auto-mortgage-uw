class InfrastructureException(Exception):
    """Base exception for infrastructure module."""
    pass

class DeploymentNotFoundException(InfrastructureException):
    """Raised when a deployment is not found."""
    pass

class ServiceHealthNotFoundException(InfrastructureException):
    """Raised when service health information is not found."""
    pass

class ConfigurationSaveException(InfrastructureException):
    """Raised when saving infrastructure configuration fails."""
    pass

class HealthCheckException(InfrastructureException):
    """Raised when health check operations fail."""
    pass