from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, field_validator

# Address Schemas


class PropertyAddress(BaseModel):
    street: str = Field(..., description="Street address")
    city: str = Field(..., description="City name")
    province: str = Field(..., min_length=2, max_length=2, description="Province code (e.g., ON)")
    postal_code: str = Field(..., pattern=r"^[A-Za-z]\d[A-Za-z] ?\d[A-Za-z]\d$", description="Postal code in A1A 1A1 format")
    country: str = Field(default="Canada", description="Country name")


class PropertyAddressDB(PropertyAddress):
    model_config = ConfigDict(from_attributes=True)


# Client Schemas


class ClientBase(BaseModel):
    employment_status: str = Field(..., description="Employment status")
    employer_name: Optional[str] = Field(None, max_length=255)
    years_employed: Optional[int] = Field(None, ge=0)
    annual_income: Decimal = Field(..., gt=0, description="Annual income in CAD")
    other_income: Optional[Decimal] = Field(None, ge=0, description="Other income in CAD")
    credit_score: Optional[int] = Field(None, ge=300, le=900, description="Credit score between 300-900")
    marital_status: Optional[str] = Field(None, description="Marital status")


class ClientCreate(ClientBase):
    sin: str = Field(..., min_length=9, max_length=9, description="Social Insurance Number (9 digits)")
    date_of_birth: datetime = Field(..., description="Date of birth (will be encrypted)")

    @field_validator('date_of_birth')
    def validate_date_of_birth(cls, v):  # FIXED: Added validation for date of birth
        if v > datetime.now():
            raise ValueError('Date of birth cannot be in the future')
        return v


class ClientUpdate(ClientBase):
    pass


class ClientResponse(ClientBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


# Co-Borrower Schemas


class CoBorrowerBase(BaseModel):
    full_name: str = Field(..., description="Full legal name")
    sin: str = Field(..., min_length=9, max_length=9, description="Social Insurance Number (9 digits)")
    date_of_birth: datetime = Field(..., description="Date of birth (will be encrypted)")  # FIXED: Added DOB field
    annual_income: Decimal = Field(..., gt=0, description="Annual income in CAD")
    employment_status: str = Field(..., description="Employment status")
    credit_score: Optional[int] = Field(None, ge=300, le=900, description="Credit score between 300-900")

    @field_validator('date_of_birth')
    def validate_date_of_birth(cls, v):  # FIXED: Added validation for date of birth
        if v > datetime.now():
            raise ValueError('Date of birth cannot be in the future')
        return v


class CoBorrowerCreate(CoBorrowerBase):
    pass


class CoBorrowerResponse(CoBorrowerBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


# Application Schemas


class ApplicationBase(BaseModel):
    application_type: str = Field(..., pattern="^(purchase|refinance|renewal)$", description="Type of application")
    property_address: PropertyAddress
    property_type: str = Field(..., pattern="^(single_family|condo|townhouse|multi_unit)$", description="Type of property")
    property_value: Decimal = Field(..., gt=0, description="Estimated market value of the property")
    purchase_price: Optional[Decimal] = Field(None, gt=0, description="Purchase price (required for purchase applications)")
    down_payment: Optional[Decimal] = Field(None, ge=0, description="Down payment amount")
    requested_loan_amount: Decimal = Field(..., gt=0, description="Requested loan amount")
    amortization_years: int = Field(..., ge=5, le=30, description="Amortization period in years (5-30)")
    term_years: int = Field(..., ge=1, le=10, description="Mortgage term in years (1-10)")
    mortgage_type: str = Field(..., pattern="^(fixed|variable|adjustable)$", description="Type of mortgage")

    @field_validator('down_payment')
    def validate_down_payment(cls, v, info):
        if info.data.get('application_type') == 'purchase' and v is None:
            raise ValueError('down_payment is required for purchase applications')
        return v

    @field_validator('requested_loan_amount')
    def validate_loan_amount(cls, v, info):  # FIXED: Added loan amount validation
        if 'property_value' in info.data and 'down_payment' in info.data:
            property_value = info.data['property_value']
            down_payment = info.data['down_payment'] or Decimal('0')
            if v > (property_value - down_payment):
                raise ValueError('Requested loan amount cannot exceed property value minus down payment')
        return v


class ApplicationCreate(ApplicationBase):
    client_id: int = Field(..., description="Client ID for the application")
    co_borrowers: Optional[List[CoBorrowerCreate]] = Field(None, description="List of co-borrowers")


class ApplicationUpdate(ApplicationBase):
    pass


class ApplicationResponse(ApplicationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int
    broker_id: Optional[int]
    status: str
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime]


class ApplicationSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_full_name: str
    property_address: PropertyAddress
    property_value: Decimal
    requested_loan_amount: Decimal
    status: str
    created_at: datetime
    submitted_at: Optional[datetime]