from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Boolean, Text, Index, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from decimal import Decimal
from typing import List
from mortgage_underwriting.common.database import Base

class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (
        Index('ix_clients_email', 'email'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(20))
    date_of_birth_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    sin_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    addresses: Mapped[List["ClientAddress"]] = relationship("ClientAddress", back_populates="client", cascade="all, delete-orphan")
    applications: Mapped[List["MortgageApplication"]] = relationship("MortgageApplication", back_populates="client", lazy="selectin")

class ClientAddress(Base):
    __tablename__ = "client_addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    street: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    province: Mapped[str] = mapped_column(String(50), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(10), nullable=False)
    country: Mapped[str] = mapped_column(String(50), nullable=False, default="Canada")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # FIXED: Added updated_at field

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="addresses")

class MortgageApplication(Base):
    __tablename__ = "mortgage_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)  # FIXED: Added ondelete=CASCADE
    property_value: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    down_payment: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    loan_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)  # FIXED: Changed from Float to Decimal
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    amortization_period: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="applications")