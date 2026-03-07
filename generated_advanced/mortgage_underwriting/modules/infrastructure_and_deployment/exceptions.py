from mortgage_underwriting.common.exceptions import AppException

class InfrastructureDeploymentError(AppException):
    """Base exception for infrastructure and deployment module."""
    pass

class ServiceNotFoundError(InfrastructureDeploymentError):
    """Raised when a requested service is not found."""
    def __init__(self, service_name: str):
        self.service_name = service_name
        super().__init__(f"Service '{service_name}' not found.")

class DeploymentStatusNotFoundError(InfrastructureDeploymentError):
    """Raised when no deployment status records are found."""
    def __init__(self):
        super().__init__("No deployment status records found.")

class SystemHealthNotFoundError(InfrastructureDeploymentError):
    """Raised when no system health records are found."""
    def __init__(self):
        super().__init__("No system health records found.")