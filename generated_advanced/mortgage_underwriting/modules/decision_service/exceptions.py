```python
from mortgage_underwriting.common.exceptions import AppException

class DecisionServiceError(AppException):
    """Base exception for Decision Service"""
    pass

class InvalidFinancialAmountError(DecisionServiceError):
    """Raised when financial amounts are invalid"""
    error_code = "INVALID_FINANCIAL_AMOUNT"
    detail = "Financial amounts must be positive values"

class DecisionNotFoundError(DecisionServiceError):
    """Raised when decision audit cannot be found"""
    error_code = "DECISION_NOT_FOUND"
    detail = "Decision audit record not found"

class PaginationLimitExceededError(DecisionServiceError):
    """Raised when pagination limit exceeds allowed maximum"""
    error_code = "PAGINATION_LIMIT_EXCEEDED"
    detail = "Pagination limit cannot exceed 100 items per request"
```

This implementation addresses all five issues identified:

1. **Financial precision**: Changed `FLOAT` columns to `Numeric(19, 4)` for both `interest_rate` and `loan_amount`
2. **Timestamp integrity**: Added `updated_at` field with `onupdate=func.now()` to the `DecisionAudit` model
3. **Foreign key indexing**: Added proper indexes on `application_id` and `user_id` foreign keys using `Index()`
4. **SQLAlchemy 2.0 compliance**: Updated relationships to use `Mapped[T] = relationship(...)` pattern with `back_populates`
5. **Pagination support**: Implemented proper pagination in the service layer with `skip`/`limit` parameters and enforced maximum limit of 100 items per page

The changes are surgical and focused only on the specific issues mentioned, maintaining the overall structure and functionality while bringing it into compliance with all requirements.