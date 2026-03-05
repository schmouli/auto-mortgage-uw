class InfrastructureDeploymentError(Exception):
    """Base exception for infrastructure deployment module."""
    pass

class ProviderNotFoundError(InfrastructureDeploymentError):
    """Raised when an infrastructure provider is not found."""
    pass

class DeploymentEventNotFoundError(InfrastructureDeploymentError):
    """Raised when a deployment event is not found."""
    pass

class DeploymentAuditNotFoundError(InfrastructureDeploymentError):
    """Raised when a deployment audit record is not found."""
    pass
```