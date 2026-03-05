```
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
    interest_rate: Decimal = Field(..., gt=0, description="Interest rate as decimal (e.g., 0.035 for 3.5%)")
    term_months: int = Field(..., gt=0, description="Loan term in months")
    min_credit_score: int = Field(..., ge=300, le=850, description="Minimum credit score required")
    max_loan_amount: Decimal = Field(..., gt=0, description="Maximum loan amount in CAD")

class ProductCreate(ProductBase):
    lender_id: int = Field(..., description="FK to lenders table")

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255, description="Product name")
    description: Optional[str] = Field(None, description="Product description")
    interest_rate: Optional[Decimal] = Field(None, gt=0, description="Interest rate as decimal")
    term_months: Optional[int] = Field(None, gt=0, description="Loan term in months")
    min_credit_score: Optional[int] = Field(None, ge=300, le=850, description="Minimum credit score required")
    max_loan_amount: Optional[Decimal] = Field(None, gt=0, description="Maximum loan amount in CAD")

class ProductResponse(ProductBase):
    id: int = Field(..., description="Product ID")
    lender_id: int = Field(..., description="FK to lenders table")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True

# Application Schemas
class ApplicationBase(BaseModel):
    client_id: int = Field(..., description="FK to users table")
    product_id: int = Field(..., description="FK to products table")
    loan_amount: Decimal = Field(..., gt=0, description="Requested loan amount in CAD")
    property_value: Decimal = Field(..., gt=0, description="Property value in CAD")

class ApplicationCreate(ApplicationBase):
    pass

class ApplicationUpdate(BaseModel):
    status: Optional[str] = Field(None, description="Application status")
    loan_amount: Optional[Decimal] = Field(None, gt=0, description="Requested loan amount in CAD")
    property_value: Optional[Decimal] = Field(None, gt=0, description="Property value in CAD")

class ApplicationResponse(ApplicationBase):
    id: int = Field(..., description="Application ID")
    status: str = Field(..., description="Application status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True

# Document Schemas
class DocumentBase(BaseModel):
    application_id: int = Field(..., description="FK to applications table")
    document_type: str = Field(..., description="Type of document")
    file_path: str = Field(..., description="Path to document file")

class DocumentCreate(DocumentBase):
    pass

class DocumentUpdate(BaseModel):
    document_type: Optional[str] = Field(None, description="Type of document")
    file_path: Optional[str] = Field(None, description="Path to document file")

class DocumentResponse(DocumentBase):
    id: int = Field(..., description="Document ID")
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True

# Response Schemas
class SeedDataResponse(BaseModel):
    message: str = Field(..., description="Status message")
    users_created: int = Field(default=0, description="Number of users created")
    lenders_created: int = Field(default=0, description="Number of lenders created")
    products_created: int = Field(default=0, description="Number of products created")
    applications_created: int = Field(default=0, description="Number of applications created")
    documents_created: int = Field(default=0, description="Number of documents created")

class UserListResponse(BaseModel):
    users: List[UserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Number of items returned")
```