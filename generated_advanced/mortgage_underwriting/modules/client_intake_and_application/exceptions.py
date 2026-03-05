```python
from mortgage_underwriting.common.exceptions import AppException


class ApplicationNotFoundError(AppException):
    def __init__(self, message: str = "Application not found"):
        super().__init__("APPLICATION_NOT_FOUND", message)


class InvalidFinancialDataError(AppException):
    def __init__(self, message: str = "Invalid financial data provided"):
        super().__init__("INVALID_FINANCIAL_DATA", message)
```