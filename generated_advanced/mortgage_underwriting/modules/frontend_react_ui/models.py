from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Boolean, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from decimal import Decimal
from mortgage_underwriting.common.database import Base


class MortgageApplication(Base):
    __tablename__ = "mortgage_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    down_payment: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)  # Contract rate
    property_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    amortization_period: Mapped[int] = mapped_column(Integer, nullable=False)  # In years
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="applications")


class ComplianceAuditLog(Base):
    __tablename__ = "compliance_audit_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("mortgage_applications.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)  # GDS_CALCULATION, TDS_CALCULATION, etc.
    details: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())