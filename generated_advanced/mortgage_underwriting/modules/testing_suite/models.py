```python
from sqlalchemy import Column, Integer, String, DateTime, Numeric, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
from decimal import Decimal
from typing import Optional
import uuid

Base = declarative_base()

class AuditMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    changed_by = Column(String(255), nullable=True)  # User ID or system identifier


class TestRun(Base, AuditMixin):
    __tablename__ = 'test_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), unique=True, default=lambda: str(uuid.uuid4()), nullable=False)
    suite_name = Column(String(255), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    passed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    coverage_percentage = Column(Numeric(precision=5, scale=2))  # e.g., 98.75%
    is_success = Column(Boolean, default=False)

    def update_stats(self):
        self.total_count = self.passed_count + self.failed_count + self.skipped_count
        if self.total_count > 0:
            self.coverage_percentage = Decimal((self.passed_count + self.skipped_count) / self.total_count * 100).quantize(Decimal('0.01'))
        else:
            self.coverage_percentage = Decimal('0')
        self.is_success = self.failed_count == 0 and self.total_count >= 1


class TestCase(Base, AuditMixin):
    __tablename__ = 'test_cases'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(1000))
    module = Column(String(100), nullable=False, index=True)  # e.g., underwriting, fintrac
    category = Column(String(100), nullable=False)  # unit, integration, e2e
    expected_result = Column(String(500))
    actual_result = Column(String(500))
    status = Column(String(50), default='pending')  # pending, pass, fail, skip
    execution_time_ms = Column(Integer)
    test_run_id = Column(String(36), ForeignKey('test_runs.run_id'), nullable=False)
    
    test_run = relationship("TestRun", backref="test_cases")

    def set_status(self, result: str, actual_res: Optional[str] = None, exec_time: Optional[int] = None):
        valid_statuses = ['pass', 'fail', 'skip']
        if result not in valid_statuses:
            raise ValueError(f"Invalid status '{result}'. Must be one of {valid_statuses}")
        
        self.status = result
        self.actual_result = actual_res or ''
        self.execution_time_ms = exec_time or 0
```

---