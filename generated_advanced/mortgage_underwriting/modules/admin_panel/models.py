from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Boolean, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from decimal import Decimal
from mortgage_underwriting.common.database import Base

class MortgageApplication(Base):
    __tablename__ = "mortgage_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)  # NEVER float
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="applications")

# FIXED: Added constants for regulatory thresholds (avoid hardcoded values)
QUALIFYING_RATE_FLOOR = Decimal('5.25')
MAX_GDS_RATIO = Decimal('0.39')
MAX_TDS_RATIO = Decimal('0.44')