from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Enum,
    Text,
    Numeric,
    Boolean,
    Index,
    UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base
import enum

Base = declarative_base()

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    BROKER = "broker"
    CLIENT = "client"

class ApplicationStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"

class DocumentType(str, enum.Enum):
    INCOME_VERIFICATION = "income_verification"
    PROPERTY_APPRAISAL = "property_appraisal"
    CREDIT_REPORT = "credit_report"
    IDENTIFICATION = "identification"

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)  # Never store plain text passwords
    role = Column(Enum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    changed_by = Column(String(255), nullable=True)
    
    # Relationships
    applications = relationship("Application", back_populates="client")
    sessions = relationship("UserSession", back_populates="user")
    
    __table_args__ = (
        Index('idx_users_email', 'email'),
        Index('idx_users_role', 'role'),
        Index('ix_user_email_active', 'email', 'is_active'),  # FIXED: Added composite index for optimized login/lookup
    )

class UserSession(Base):
    __tablename__ = 'user_sessions'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)  # FIXED: Added ondelete=CASCADE
    session_token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="sessions")

class Lender(Base):
    __tablename__ = 'lenders'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    changed_by = Column(String(255), nullable=True)
    
    # Relationships
    products = relationship("Product", back_populates="lender")

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True, index=True)
    lender_id = Column(Integer, ForeignKey("lenders.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    interest_rate = Column(Numeric(19, 4), nullable=False)  # FIXED: Changed from float to Numeric(19, 4) for precision
    term_months = Column(Integer, nullable=False)
    min_credit_score = Column(Integer, nullable=False)
    max_loan_amount = Column(Numeric(15, 2), nullable=False)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    changed_by = Column(String(255), nullable=True)
    
    # Relationships
    lender = relationship("Lender", back_populates="products")
    applications = relationship("Application", back_populates="product")

class Application(Base):
    __tablename__ = 'applications'
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.DRAFT, nullable=False)
    loan_amount = Column(Numeric(15, 2), nullable=False)
    property_value = Column(Numeric(15, 2), nullable=False)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    changed_by = Column(String(255), nullable=True)
    
    # Relationships
    client = relationship("User", back_populates="applications")
    product = relationship("Product", back_populates="applications")
    documents = relationship("Document", back_populates="application")

class Document(Base):
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    document_type = Column(Enum(DocumentType), nullable=False)
    file_path = Column(String(500), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    changed_by = Column(String(255), nullable=True)
    
    # Relationships
    application = relationship("Application", back_populates="documents")
```

```