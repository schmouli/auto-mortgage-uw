```python
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, validator

# User Schemas
class UserBase(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    role: str = Field(..., description="User role (admin/broker/client)")

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="User password")

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = Field(None, description="User email address")
    role: Optional[str] = Field(None, description="User role")
    is_active: Optional[bool] = Field(None, description="Account active status")

class UserResponse(UserBase):
    id: int = Field(..., description="User ID")
    is_active: bool = Field(..., description="Account active status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True

# Lender Schemas
class LenderBase(BaseModel):
    name: str = Field(..., max_length=255, description="Lender name")
    description: Optional[str] = Field(None, description="Lender description")

class LenderCreate(LenderBase):
    pass

class LenderUpdate(LenderBase):
    name: Optional[str] = Field(None, max_length=255, description="Lender name")
    description: Optional[str] = Field(None, description="Lender description")

class LenderResponse(LenderBase):
    id: int = Field(..., description="Lender ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True

# Product Schemas
class ProductBase(BaseModel):
    name: str = Field(..., max_length=255, description="Product name")
    description: Optional[str] = Field(None, description="Product description")
    interest_rate: Decimal = Field(..., description="Interest rate (e.g., 0.0375 for 3.75%)")
    term_months: int = Field(..., description="Term in months (e.g., 60 for 5 years)")
    
    @validator('interest_rate')
    def validate_interest_rate(cls, v):
        if v < 0 or v > 1:
            raise ValueError('Interest rate must be between 0 and 1')
        return v

class ProductCreate(ProductBase):
    lender_id: int = Field(..., description="Lender ID")

class ProductUpdate(ProductBase):
    name: Optional[str] = Field(None, max_length=255, description="Product name")
    interest_rate: Optional[Decimal] = Field(None, description="Interest rate")
    term_months: Optional[int] = Field(None, description="Term in months")

class ProductResponse(ProductBase):
    id: int = Field(..., description="Product ID")
    lender_id: int = Field(..., description="Lender ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True

# Application Schemas
class ApplicationBase(BaseModel):
    loan_amount: Decimal = Field(..., description="Loan amount requested")
    property_value: Decimal = Field(..., description="Property value")
    down_payment: Decimal = Field(..., description="Down payment amount")
    
    @validator('loan_amount', 'property_value', 'down_payment')
    def validate_positive_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be positive')
        return v

class ApplicationCreate(ApplicationBase):
    client_id: int = Field(..., description="Client user ID")
    product_id: int = Field(..., description="Product ID")

class ApplicationUpdate(ApplicationBase):
    loan_amount: Optional[Decimal] = Field(None, description="Loan amount requested")
    property_value: Optional[Decimal] = Field(None, description="Property value")
    down_payment: Optional[Decimal] = Field(None, description="Down payment amount")
    status: Optional[str] = Field(None, description="Application status")
    uw_decision: Optional[str] = Field(None, description="Underwriting decision")
    uw_risk_score: Optional[int] = Field(None, description="Risk score (0-999)")

class ApplicationResponse(ApplicationBase):
    id: int = Field(..., description="Application ID")
    client_id: int = Field(..., description="Client user ID")
    product_id: int = Field(..., description="Product ID")
    status: str = Field(..., description="Application status")
    uw_decision: Optional[str] = Field(None, description="Underwriting decision")
    uw_risk_score: Optional[int] = Field(None, description="Risk score (0-999)")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True

# Document Schemas
class DocumentBase(BaseModel):
    document_type: str = Field(..., description="Document type")
    file_name: str = Field(..., description="Original file name")

class DocumentCreate(DocumentBase):
    application_id: int = Field(..., description="Application ID")
    file_path: str = Field(..., description="Path to encrypted file")

class DocumentUpdate(DocumentBase):
    document_type: Optional[str] = Field(None, description="Document type")
    file_name: Optional[str] = Field(None, description="Original file name")

class DocumentResponse(DocumentBase):
    id: int = Field(..., description="Document ID")
    application_id: int = Field(..., description="Application ID")
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True

# Seed Data Response Schema
class SeedDataResponse(BaseModel):
    message: str = Field(..., description="Seed data operation result")
    users_created: int = Field(..., description="Number of users created")
    lenders_created: int = Field(..., description="Number of lenders created")
    products_created: int = Field(..., description="Number of products created")
    applications_created: int = Field(..., description="Number of applications created")
    documents_created: int = Field(..., description="Number of documents created")
```