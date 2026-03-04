```python
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
    
    __table_args__ = (
        Index('idx_users_email', 'email'),
        Index('idx_users_role', 'role'),
    )

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
    
    __table_args__ = (
        Index('idx_lenders_name', 'name'),
    )

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True, index=True)
    lender_id = Column(Integer, ForeignKey('lenders.id'), nullable=False)
    name = Column(String(255), nullable=False)  # e.g., "5-Year Fixed"
    description = Column(Text, nullable=True)
    interest_rate = Column(Numeric(precision=5, scale=4), nullable=False)  # e.g., 0.0375 for 3.75%
    term_months = Column(Integer, nullable=False)  # e.g., 60 for 5 years
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    changed_by = Column(String(255), nullable=True)
    
    # Relationships
    lender = relationship("Lender", back_populates="products")
    applications = relationship("Application", back_populates="product")
    
    __table_args__ = (
        UniqueConstraint('lender_id', 'name', name='uq_product_lender_name'),
        Index('idx_products_lender', 'lender_id'),
    )

class Application(Base):
    __tablename__ = 'applications'
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.DRAFT, nullable=False)
    
    # Financial information
    loan_amount = Column(Numeric(precision=12, scale=2), nullable=False)  # e.g., $500,000.00
    property_value = Column(Numeric(precision=12, scale=2), nullable=False)  # e.g., $750,000.00
    down_payment = Column(Numeric(precision=12, scale=2), nullable=False)  # e.g., $150,000.00
    
    # Underwriting result
    uw_decision = Column(String(50), nullable=True)  # e.g., "Approved", "Declined"
    uw_risk_score = Column(Integer, nullable=True)  # Risk score from 0-999
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    changed_by = Column(String(255), nullable=True)
    
    # Relationships
    client = relationship("User", back_populates="applications")
    product = relationship("Product", back_populates="applications")
    documents = relationship("Document", back_populates="application")
    
    __table_args__ = (
        Index('idx_applications_client', 'client_id'),
        Index('idx_applications_product', 'product_id'),
        Index('idx_applications_status', 'status'),
    )

class Document(Base):
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey('applications.id'), nullable=False)
    document_type = Column(Enum(DocumentType), nullable=False)
    file_path = Column(String(500), nullable=False)  # Path to encrypted file storage
    file_name = Column(String(255), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    changed_by = Column(String(255), nullable=True)
    
    # Relationships
    application = relationship("Application", back_populates="documents")
    
    __table_args__ = (
        Index('idx_documents_application', 'application_id'),
        Index('idx_documents_type', 'document_type'),
    )
```