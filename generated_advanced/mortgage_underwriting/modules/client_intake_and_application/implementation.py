```python
# --- models.py ---

from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime, ForeignKey, Boolean,
    CheckConstraint, Text, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from decimal import Decimal
from datetime import datetime
from typing import Optional
import uuid

from app.db.base_class import Base


class Client(Base):
    __tablename__ = "clients"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, 
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    sin_encrypted: Mapped[str] = mapped_column(String(255))
    date_of_birth_encrypted: Mapped[str] = mapped_column(String(255))
    employment_status: Mapped[str] = mapped_column(String(50))
    employer_name: Mapped[Optional[str]] = mapped_column(String(255))
    years_employed: Mapped[int] = mapped_column(Integer)
    annual_income: Mapped[Decimal] = mapped_column(Numeric(precision=15, scale=2))
    other_income: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=15, scale=2))
    credit_score: Mapped[int] = mapped_column(Integer)
    marital_status: Mapped[str] = mapped_column(String(20))
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))

    # Relationships
    applications: Mapped[list["Application"]] = relationship(back_populates="client")
    user: Mapped["User"] = relationship(foreign_keys=[user_id])

    # Constraints
    __table_args__ = (
        CheckConstraint('annual_income >= 0', name='check_annual_income_positive'),
        CheckConstraint('credit_score >= 300 AND credit_score <= 900', name='check_credit_score_range'),
    )


class Application(Base):
    __tablename__ = "applications"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, 
        default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"))
    broker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brokers.id"))
    application_type: Mapped[str] = mapped_column(String(50))  # Purchase, Refinance, Renewal
    status: Mapped[str] = mapped_column(String(50), default="draft")  # draft, submitted, under_review, approved, denied
    
    # Property details
    property_address: Mapped[str] = mapped_column(Text)
    property_type: Mapped[str] = mapped_column(String(100))
    property_value: Mapped[Decimal] = mapped_column(Numeric(precision=15, scale=2))
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(precision=15, scale=2))
    down_payment: Mapped[Decimal] = mapped_column(Numeric(precision=15, scale=2))
    requested_loan_amount: Mapped[Decimal] = mapped_column(Numeric(precision=15, scale=2))
    
    # Loan terms
    amortization_years: Mapped[int] = mapped_column(Integer)
    term_years: Mapped[int] = mapped_column(Integer)
    mortgage_type: Mapped[str] = mapped_column(String(50))  # Conventional, High-Ratio, etc.
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))

    # Relationships
    client: Mapped["Client"] = relationship(back_populates="applications")
    co_borrowers: Mapped[list["CoBorrower"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    broker: Mapped["Broker"] = relationship(foreign_keys=[broker_id])

    # Constraints
    __table_args__ = (
        CheckConstraint('purchase_price > 0', name='check_purchase_price_positive'),
        CheckConstraint('amortization_years BETWEEN 5 AND 30', name='check_amortization_years_range'),
        CheckConstraint('term_years BETWEEN 1 AND 10', name='check_term_years_range'),
        Index('idx_application_client_id', 'client_id'),
        Index('idx_application_broker_id', 'broker_id'),
        Index('idx_application_status', 'status')
    )


class CoBorrower(Base):
    __tablename__ = "co_borrowers"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, 
        default=uuid.uuid4
    )
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"))
    full_name: Mapped[str] = mapped_column(String(255))
    sin_encrypted: Mapped[str] = mapped_column(String(255))
    annual_income: Mapped[Decimal] = mapped_column(Numeric(precision=15, scale=2))
    employment_status: Mapped[str] = mapped_column(String(50))
    credit_score: Mapped[int] = mapped_column(Integer)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))

    # Relationships
    application: Mapped["Application"] = relationship(back_populates="co_borrowers")

    # Constraints
    __table_args__ = (
        CheckConstraint('annual_income >= 0', name='check_co_borrower_annual_income_positive'),
        CheckConstraint('credit_score >= 300 AND credit_score <= 900', name='check_co_borrower_credit_score_range'),
    )

```

```python
# --- schemas.py ---

from pydantic import BaseModel, Field, validator, root_validator
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from enum import Enum
import uuid


class EmploymentStatusEnum(str, Enum):
    employed = "employed"
    self_employed = "self-employed"
    unemployed = "unemployed"
    retired = "retired"
    student = "student"


class MaritalStatusEnum(str, Enum):
    single = "single"
    married = "married"
    separated = "separated"
    divorced = "divorced"
    widowed = "widowed"


class ApplicationTypeEnum(str, Enum):
    purchase = "purchase"
    refinance = "refinance"
    renewal = "renewal"


class ApplicationStatusEnum(str, Enum):
    draft = "draft"
    submitted = "submitted"
    under_review = "under_review"
    approved = "approved"
    denied = "denied"


class PropertyTypeEnum(str, Enum):
    detached = "detached"
    semi_detached = "semi-detached"
    townhouse = "townhouse"
    condo = "condo"
    duplex = "duplex"
    triplex = "triplex"
    four_plex = "four-plex"


class MortgageTypeEnum(str, Enum):
    conventional = "conventional"
    high_ratio = "high-ratio"
    private = "private"


# Client Schemas
class ClientCreateRequest(BaseModel):
    sin: str = Field(..., description="Social Insurance Number")
    date_of_birth: str = Field(..., description="Date of birth in YYYY-MM-DD format")
    employment_status: EmploymentStatusEnum
    employer_name: Optional[str] = None
    years_employed: int = Field(..., ge=0)
    annual_income: Decimal = Field(..., gt=0)
    other_income: Optional[Decimal] = Field(None, ge=0)
    credit_score: int = Field(..., ge=300, le=900)
    marital_status: MaritalStatusEnum


class ClientUpdateRequest(ClientCreateRequest):
    pass


class ClientResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    employment_status: EmploymentStatusEnum
    employer_name: Optional[str]
    years_employed: int
    annual_income: Decimal
    other_income: Optional[Decimal]
    credit_score: int
    marital_status: MaritalStatusEnum
    created_at: datetime
    updated_at: datetime


# Co-Borrower Schemas
class CoBorrowerCreateRequest(BaseModel):
    full_name: str
    sin: str = Field(..., description="Social Insurance Number")
    annual_income: Decimal = Field(..., gt=0)
    employment_status: EmploymentStatusEnum
    credit_score: int = Field(..., ge=300, le=900)


class CoBorrowerUpdateRequest(CoBorrowerCreateRequest):
    pass


class CoBorrowerResponse(CoBorrowerCreateRequest):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


# Application Schemas
class ApplicationCreateRequest(BaseModel):
    broker_id: uuid.UUID
    application_type: ApplicationTypeEnum
    
    # Property details
    property_address: str
    property_type: PropertyTypeEnum
    property_value: Decimal = Field(..., gt=0)
    purchase_price: Decimal = Field(..., gt=0)
    down_payment: Decimal = Field(..., ge=0)
    requested_loan_amount: Decimal = Field(..., gt=0)
    
    # Loan terms
    amortization_years: int = Field(..., ge=5, le=30)
    term_years: int = Field(..., ge=1, le=10)
    mortgage_type: MortgageTypeEnum
    
    # Validation
    @root_validator
    def validate_loan_amount(cls, values):
        purchase_price = values.get('purchase_price')
        down_payment = values.get('down_payment')
        requested_loan_amount = values.get('requested_loan_amount')
        
        if purchase_price and down_payment and requested_loan_amount:
            calculated_loan = purchase_price - down_payment
            if requested_loan_amount != calculated_loan:
                raise ValueError("Requested loan amount must equal purchase price minus down payment")
                
        return values


class ApplicationUpdateRequest(ApplicationCreateRequest):
    pass


class ApplicationResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    broker_id: uuid.UUID
    application_type: ApplicationTypeEnum
    status: ApplicationStatusEnum
    
    # Property details
    property_address: str
    property_type: PropertyTypeEnum
    property_value: Decimal
    purchase_price: Decimal
    down_payment: Decimal
    requested_loan_amount: Decimal
    
    # Loan terms
    amortization_years: int
    term_years: int
    mortgage_type: MortgageTypeEnum
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime]
    
    # Related data
    co_borrowers: List[CoBorrowerResponse] = []

    class Config:
        orm_mode = True


# Summary Schema for PDF generation
class ApplicationSummaryResponse(BaseModel):
    application_id: uuid.UUID
    client_name: str
    client_email: str
    property_address: str
    property_value: Decimal
    purchase_price: Decimal
    down_payment: Decimal
    requested_loan_amount: Decimal
    amortization_years: int
    term_years: int
    mortgage_type: str
    application_date: datetime
    submission_date: Optional[datetime]
    status: str

```

```python
# --- services.py ---

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, desc
from typing import List, Optional, Dict, Any
import uuid
from decimal import Decimal

from app.models.client_intake import Client, Application, CoBorrower
from app.schemas.client_intake import (
    ClientCreateRequest, ClientUpdateRequest,
    ApplicationCreateRequest, ApplicationUpdateRequest,
    CoBorrowerCreateRequest, CoBorrowerUpdateRequest
)
from app.core.security import encrypt_data
from app.exceptions.client_intake import (
    ApplicationNotFoundError, ClientAccessDeniedError,
    BrokerAccessDeniedError, InvalidLoanAmountError
)
from app.models.user import User


class ClientIntakeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_client(self, user_id: uuid.UUID, client_data: ClientCreateRequest) -> Client:
        """Create a new client record with encrypted PII"""
        # Encrypt sensitive data
        sin_encrypted = encrypt_data(client_data.sin)
        dob_encrypted = encrypt_data(client_data.date_of_birth)
        
        # Create client object
        client = Client(
            user_id=user_id,
            sin_encrypted=sin_encrypted,
            date_of_birth_encrypted=dob_encrypted,
            employment_status=client_data.employment_status.value,
            employer_name=client_data.employer_name,
            years_employed=client_data.years_employed,
            annual_income=client_data.annual_income,
            other_income=client_data.other_income,
            credit_score=client_data.credit_score,
            marital_status=client_data.marital_status.value,
            changed_by=user_id
        )
        
        self.db.add(client)
        await self.db.commit()
        await self.db.refresh(client)
        return client

    async def get_client_applications(self, user_id: uuid.UUID, client_id: uuid.UUID) -> List[Application]:
        """Get all applications for a specific client (client can only see their own)"""
        # Verify client belongs to user
        result = await self.db.execute(
            select(Client).where(Client.id == client_id, Client.user_id == user_id)
        )
        client = result.scalar_one_or_none()
        
        if not client:
            raise ClientAccessDeniedError("Client does not belong to user")
            
        # Fetch applications
        result = await self.db.execute(
            select(Application)
            .options(selectinload(Application.co_borrowers))
            .where(Application.client_id == client_id)
            .order_by(desc(Application.created_at))
        )
        return result.scalars().all()

    async def create_application(self, user_id: uuid.UUID, client_id: uuid.UUID, 
                               app_data: ApplicationCreateRequest) -> Application:
        """Create a new mortgage application"""
        # Verify client belongs to user
        result = await self.db.execute(
            select(Client).where(Client.id == client_id, Client.user_id == user_id)
        )
        client = result.scalar_one_or_none()
        
        if not client:
            raise ClientAccessDeniedError("Client does not belong to user")
            
        # Validate loan amount calculation
        calculated_loan = app_data.purchase_price - app_data.down_payment
        if app_data.requested_loan_amount != calculated_loan:
            raise InvalidLoanAmountError("Requested loan amount must equal purchase price minus down payment")
            
        # Create application
        application = Application(
            client_id=client_id,
            broker_id=app_data.broker_id,
            application_type=app_data.application_type.value,
            property_address=app_data.property_address,
            property_type=app_data.property_type.value,
            property_value=app_data.property_value,
            purchase_price=app_data.purchase_price,
            down_payment=app_data.down_payment,
            requested_loan_amount=app_data.requested_loan_amount,
            amortization_years=app_data.amortization_years,
            term_years=app_data.term_years,
            mortgage_type=app_data.mortgage_type.value,
            changed_by=user_id
        )
        
        self.db.add(application)
        await self.db.commit()
        await self.db.refresh(application)
        return application

    async def get_application(self, user_id: uuid.UUID, application_id: uuid.UUID, 
                            user_role: str = "client") -> Application:
        """Get a specific application by ID with access control"""
        query = select(Application).options(selectinload(Application.co_borrowers))
        
        if user_role == "client":
            query = query.join(Client).where(
                and_(
                    Application.id == application_id,
                    Client.user_id == user_id
                )
            )
        elif user_role == "broker":
            query = query.where(
                and_(
                    Application.id == application_id,
                    Application.broker_id == user_id
                )
            )
        else:
            raise ValueError("Invalid user role")
            
        result = await self.db.execute(query)
        application = result.scalar_one_or_none()
        
        if not application:
            if user_role == "client":
                raise ClientAccessDeniedError("Application not found or access denied")
            else:
                raise BrokerAccessDeniedError("Application not found or access denied")
                
        return application

    async def update_application(self, user_id: uuid.UUID, application_id: uuid.UUID,
                               app_data: ApplicationUpdateRequest) -> Application:
        """Update an existing application"""
        # Fetch application with access control
        application = await self.get_application(user_id, application_id, "client")
        
        # Validate loan amount calculation
        calculated_loan = app_data.purchase_price - app_data.down_payment
        if app_data.requested_loan_amount != calculated_loan:
            raise InvalidLoanAmountError("Requested loan amount must equal purchase price minus down payment")
            
        # Update fields
        application.broker_id = app_data.broker_id
        application.application_type = app_data.application_type.value
        application.property_address = app_data.property_address
        application.property_type = app_data.property_type.value
        application.property_value = app_data.property_value
        application.purchase_price = app_data.purchase_price
        application.down_payment = app_data.down_payment
        application.requested_loan_amount = app_data.requested_loan_amount
        application.amortization_years = app_data.amortization_years
        application.term_years = app_data.term_years
        application.mortgage_type = app_data.mortgage_type.value
        application.changed_by = user_id
        
        await self.db.commit()
        await self.db.refresh(application)
        return application

    async def submit_application(self, user_id: uuid.UUID, application_id: uuid.UUID) -> Application:
        """Submit an application for underwriting"""
        application = await self.get_application(user_id, application_id, "client")
        application.status = "submitted"
        application.submitted_at = datetime.utcnow()
        application.changed_by = user_id
        
        await self.db.commit()
        await self.db.refresh(application)
        return application

    async def add_co_borrower(self, user_id: uuid.UUID, application_id: uuid.UUID,
                            co_borrower_data: CoBorrowerCreateRequest) -> CoBorrower:
        """Add a co-borrower to an application"""
        # Verify application belongs to user
        application = await self.get_application(user_id, application_id, "client")
        
        # Encrypt SIN
        sin_encrypted = encrypt_data(co_borrower_data.sin)
        
        # Create co-borrower
        co_borrower = CoBorrower(
            application_id=application_id,
            full_name=co_borrower_data.full_name,
            sin_encrypted=sin_encrypted,
            annual_income=co_borrower_data.annual_income,
            employment_status=co_borrower_data.employment_status.value,
            credit_score=co_borrower_data.credit_score,
            changed_by=user_id
        )
        
        self.db.add(co_borrower)
        await self.db.commit()
        await self.db.refresh(co_borrower)
        return co_borrower

    async def get_application_summary(self, user_id: uuid.UUID, application_id: uuid.UUID) -> Dict[str, Any]:
        """Get application summary for PDF generation"""
        application = await self.get_application(user_id, application_id, "client")
        
        # Get client info
        result = await self.db.execute(
            select(User).where(User.id == application.client.user_id)
        )
        user = result.scalar_one_or_none()
        
        return {
            "application_id": application.id,
            "client_name": f"{user.first_name} {user.last_name}" if user else "Unknown",
            "client_email": user.email if user else "",
            "property_address": application.property_address,
            "property_value": application.property_value,
            "purchase_price": application.purchase_price,
            "down_payment": application.down_payment,
            "requested_loan_amount": application.requested_loan_amount,
            "amortization_years": application.amortization_years,
            "term_years": application.term_years,
            "mortgage_type": application.mortgage_type,
            "application_date": application.created_at,
            "submission_date": application.submitted_at,
            "status": application.status
        }

```

```python
# --- routes.py ---

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from app.api import deps
from app.models.user import User
from app.services.client_intake import ClientIntakeService
from app.schemas.client_intake import (
    ApplicationCreateRequest, ApplicationUpdateRequest,
    ApplicationResponse, ApplicationSummaryResponse,
    CoBorrowerCreateRequest, CoBorrowerResponse
)
from app.exceptions.client_intake import (
    ApplicationNotFoundError, ClientAccessDeniedError,
    BrokerAccessDeniedError
)

router = APIRouter(prefix="/applications", tags=["Client Intake & Applications"])


@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    application_in: ApplicationCreateRequest,
) -> ApplicationResponse:
    """
    Create a new mortgage application.
    
    Requires authentication as a client user.
    """
    try:
        service = ClientIntakeService(db)
        application = await service.create_application(
            user_id=current_user.id,
            client_id=application_in.client_id,  # This would come from the authenticated user's client profile
            app_data=application_in
        )
        return ApplicationResponse.from_orm(application)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/", response_model=List[ApplicationResponse])
async def list_applications(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> List[ApplicationResponse]:
    """
    List all applications for the authenticated user.
    
    Clients see their own applications.
    Brokers see applications assigned to them.
    """
    service = ClientIntakeService(db)
    try:
        if current_user.role == "client":
            applications = await service.get_client_applications(current_user.id, current_user.client_id)
        elif current_user.role == "broker":
            # For brokers, we'd implement a different method to get assigned applications
            applications = []  # Placeholder
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized access"
            )
        return [ApplicationResponse.from_orm(app) for app in applications]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    application_id: uuid.UUID,
) -> ApplicationResponse:
    """
    Get details of a specific application by ID.
    
    Clients can only access their own applications.
    Brokers can only access applications assigned to them.
    """
    service = ClientIntakeService(db)
    try:
        user_role = "client" if current_user.role == "client" else "broker"
        application = await service.get_application(
            user_id=current_user.id,
            application_id=application_id,
            user_role=user_role
        )
        return ApplicationResponse.from_orm(application)
    except (ApplicationNotFoundError, ClientAccessDeniedError, BrokerAccessDeniedError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    application_id: uuid.UUID,
    application_in: ApplicationUpdateRequest,
) -> ApplicationResponse:
    """
    Update an existing application.
    
    Only clients can update their own applications.
    """
    service = ClientIntakeService(db)
    try:
        application = await service.update_application(
            user_id=current_user.id,
            application_id=application_id,
            app_data=application_in
        )
        return ApplicationResponse.from_orm(application)
    except (ApplicationNotFoundError, ClientAccessDeniedError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{application_id}/submit", response_model=ApplicationResponse)
async def submit_application(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    application_id: uuid.UUID,
) -> ApplicationResponse:
    """
    Submit an application for underwriting.
    
    Only clients can submit their own applications.
    """
    service = ClientIntakeService(db)
    try:
        application = await service.submit_application(
            user_id=current_user.id,
            application_id=application_id
        )
        return ApplicationResponse.from_orm(application)
    except (ApplicationNotFoundError, ClientAccessDeniedError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{application_id}/co-borrowers", response_model=CoBorrowerResponse, status_code=status.HTTP_201_CREATED)
async def add_co_borrower(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    application_id: uuid.UUID,
    co_borrower_in: CoBorrowerCreateRequest,
) -> CoBorrowerResponse:
    """
    Add a co-borrower to an application.
    
    Only clients can add co-borrowers to their own applications.
    """
    service = ClientIntakeService(db)
    try:
        co_borrower = await service.add_co_borrower(
            user_id=current_user.id,
            application_id=application_id,
            co_borrower_data=co_borrower_in
        )
        return CoBorrowerResponse.from_orm(co_borrower)
    except (ApplicationNotFoundError, ClientAccessDeniedError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{application_id}/summary", response_model=ApplicationSummaryResponse)
async def get_application_summary(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    application_id: uuid.UUID,
) -> ApplicationSummaryResponse:
    """
    Get application summary for PDF generation.
    
    Returns structured data that can be used to generate a PDF application summary.
    """
    service = ClientIntakeService(db)
    try:
        summary_data = await service.get_application_summary(
            user_id=current_user.id,
            application_id=application_id
        )
        return ApplicationSummaryResponse(**summary_data)
    except (ApplicationNotFoundError, ClientAccessDeniedError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

```

```python
# --- exceptions.py ---

from app.exceptions.base import AppException


class ClientIntakeException(AppException):
    """Base exception for client intake module"""
    pass


class ApplicationNotFoundError(ClientIntakeException):
    """Raised when an application is not found"""
    def __init__(self, message: str = "Application not found"):
        self.message = message
        super().__init__(self.message)


class ClientAccessDeniedError(ClientIntakeException):
    """Raised when a client tries to access another client's data"""
    def __init__(self, message: str = "Access denied to client data"):
        self.message = message
        super().__init__(self.message)


class BrokerAccessDeniedError(ClientIntakeException):
    """Raised when a broker tries to access unassigned applications"""
    def __init__(self, message: str = "Access denied to application"):
        self.message = message
        super().__init__(self.message)


class InvalidLoanAmountError(ClientIntakeException):
    """Raised when loan amount calculation is invalid"""
    def __init__(self, message: str = "Invalid loan amount calculation"):
        self.message = message
        super().__init__(self.message)

```