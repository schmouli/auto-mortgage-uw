```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Boolean, Text, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from decimal import Decimal
from datetime import datetime
from mortgage_underwriting.common.database import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)  # FIXED: Added index
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    encrypted_sin: Mapped[str] = mapped_column(String, nullable=True)  # Encrypted
    encrypted_dob: Mapped[str] = mapped_column(String, nullable=True)  # Encrypted
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )  # FIXED: Added onupdate=func.now() and nullable=False

    # Relationships
    applications: Mapped[list["Application"]] = relationship("Application", back_populates="client")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("clients.id", ondelete="CASCADE"),  # FIXED: Added ondelete
        nullable=False
    )
    property_value: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    down_payment: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    loan_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)  # FIXED: Changed from Float to Decimal
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    amortization_years: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )  # FIXED: Added nullable=False

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="applications")
    lenders: Mapped[list["ApplicationLender"]] = relationship("ApplicationLender", back_populates="application")


class ApplicationLender(Base):
    __tablename__ = "application_lenders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False
    )
    lender_name: Mapped[str] = mapped_column(String(100), nullable=False)
    rate_offer: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),  # FIXED: Added onupdate=func.now()
        nullable=False
    )  # FIXED: Added nullable=False to match requirement

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="lenders")
```