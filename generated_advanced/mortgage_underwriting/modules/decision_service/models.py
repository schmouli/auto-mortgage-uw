```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Boolean, Text, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from decimal import Decimal
from mortgage_underwriting.common.database import Base

class DecisionAudit(Base):
    __tablename__ = "decision_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("mortgage_applications.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)  # FIXED: Changed from Float to Numeric(19, 4)
    loan_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)    # FIXED: Changed from Float to Numeric(19, 4)
    decision_status: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # FIXED: Added missing updated_at with onupdate

    # Relationships using Mapped types for SQLAlchemy 2.0+
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", back_populates="decisions")  # FIXED: Updated to Mapped type
    user: Mapped["User"] = relationship("User", back_populates="decision_audits")  # FIXED: Updated to Mapped type

# Indexes for foreign keys
Index('ix_decision_application_id', DecisionAudit.application_id)  # FIXED: Added index on FK
Index('ix_decision_user_id', DecisionAudit.user_id)  # FIXED: Added index on FK
```