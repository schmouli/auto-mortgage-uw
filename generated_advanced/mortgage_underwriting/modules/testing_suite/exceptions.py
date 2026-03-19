from mortgage_underwriting.common.exceptions import AppException


class TestEndpointDisabled(AppException):
    def __init__(self) -> None:
        super().__init__("TEST_001", "Test endpoints disabled in production")


class InvalidTestScenario(AppException):
    def __init__(self, scenario_name: str) -> None:
        super().__init__("TEST_002", f"Invalid scenario name: {scenario_name}")


class TestRateLimitExceeded(AppException):
    def __init__(self) -> None:
        super().__init__("TEST_003", "Test data seeding rate limit exceeded")


class InvalidTestApiKey(AppException):
    def __init__(self) -> None:
        super().__init__("TEST_004", "Invalid test API key provided")