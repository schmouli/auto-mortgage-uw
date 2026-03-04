```python
from common.exceptions import BaseMortgageException


class DeploymentNotFoundError(BaseMortgageException):
    """Raised when a deployment cannot be found."""
    
    def __init__(self, deployment_id: int):
        self.deployment_id = deployment_id
        super().__init__(f"Deployment with ID {deployment_id} not found")


class ServiceNotFoundError(BaseMortgageException):
    """Raised when a service cannot be found."""
    
    def __init__(self, service_id: int):
        self.service_id = service_id
        super().__init__(f"Service with ID {service_id} not found")


class ConfigurationNotFoundError(BaseMortgageException):
    """Raised when a configuration cannot be found."""
    
    def __init__(self, config_id: int):
        self.config_id = config_id
        super().__init__(f"Configuration with ID {config_id} not found")


class InvalidDeploymentNameError(BaseMortgageException):
    """Raised when a deployment name is invalid."""
    
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Invalid deployment name: {name}")


class DuplicateDeploymentNameError(BaseMortgageException):
    """Raised when trying to create a deployment with a duplicate name."""
    
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"A deployment with name '{name}' already exists")


class InvalidEnvironmentError(BaseMortgageException):
    """Raised when an invalid environment is provided."""
    
    def __init__(self, environment: str):
        self.environment = environment
        super().__init__(f"Invalid environment: {environment}. Must be one of development, staging, production")
```