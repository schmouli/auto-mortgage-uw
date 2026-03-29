class DeploymentException(Exception):
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class InvalidStrategyException(DeploymentException):
    def __init__(self, strategy: str):
        super().__init__(f"Invalid deployment strategy: {strategy}", "ORCHESTRATOR_003")


class DeploymentNotFoundException(DeploymentException):
    def __init__(self, deployment_id: int):
        super().__init__(f"Deployment not found: {deployment_id}", "ORCHESTRATOR_004")


class ServiceNotFoundException(DeploymentException):
    def __init__(self, service_name: str):
        super().__init__(f"Service not found: {service_name}", "ORCHESTRATOR_002")


class HealthCheckProcessingException(DeploymentException):
    def __init__(self, message: str):
        super().__init__(message, "HEALTH_CHECK_PROCESSING_ERROR")