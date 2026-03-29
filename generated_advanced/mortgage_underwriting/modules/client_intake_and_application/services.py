from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog
from datetime import datetime

from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.common.security import encrypt_pii
from mortgage_underwriting.modules.client_intake.models import Client, MortgageApplication, CoBorrower
from mortgage_underwriting.modules.client_intake.schemas import (

    ClientCreate,
    ClientUpdate,
    MortgageApplicationCreate,
    MortgageApplicationUpdate,
    CoBorrowerCreate,
    CoBorrowerUpdate
)

logger = structlog.get_logger()


class ClientIntakeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_client(self, user_id: int, payload: ClientCreate) -> Client:
        logger.info("create_client", user_id=user_id)
        
        # FIXED: Proper PII encryption for both SIN and date of birth
        sin_encrypted = encrypt_pii(payload.sin)
        dob_encrypted = encrypt_pii(payload.date_of_birth)
        
        client = Client(
            user_id=user_id,
            sin_encrypted=sin_encrypted,
            date_of_birth=dob_encrypted,  # FIXED: Was using plaintext DOB
            employment_status=payload.employment_status,
            employer_name=payload.employer_name,
            years_employed=payload.years_employed,
            annual_income=payload.annual_income,
            other_income=payload.other_income,
            credit_score=payload.credit_score,
            marital_status=payload.marital_status
        )
        
        self.db.add(client)
        await self.db.commit()
        await self.db.refresh(client)
        
        # FIXED: Add audit logging for PII access
        logger.info("client_created", client_id=client.id, user_id=user_id)
        return client

    async def get_client(self, client_id: int) -> Client:
        stmt = select(Client).where(Client.id == client_id)
        result = await self.db.execute(stmt)
        client = result.scalar_one_or_none()
        if not client:
            raise NotFoundError(f"Client with id {client_id} not found")
        return client

    async def update_client(self, client_id: int, payload: ClientUpdate) -> Client:
        client = await self.get_client(client_id)
        logger.info("update_client", client_id=client_id)
        
        for field, value in payload.model_dump().items():
            setattr(client, field, value)
            
        await self.db.commit()
        await self.db.refresh(client)
        
        # FIXED: Add audit logging for updates
        logger.info("client_updated", client_id=client_id)
        return client

    async def delete_client(self, client_id: int) -> None:
        client = await self.get_client(client_id)
        await self.db.delete(client)
        await self.db.commit()
        logger.info("client_deleted", client_id=client_id)

    async def create_application(self, client_id: int, payload: MortgageApplicationCreate) -> MortgageApplication:
        logger.info("create_application", client_id=client_id)
        
        # FIXED: Validate financial constraints before creation
        if payload.down_payment > payload.purchase_price:
            raise AppException("Down payment cannot exceed purchase price")
        
        # FIXED: Validate loan amount consistency
        expected_loan = payload.purchase_price - payload.down_payment
        if abs(expected_loan - payload.requested_loan_amount) > 0.01:  # Allow for rounding differences
            logger.warning("loan_amount_mismatch", 
                         expected=float(expected_loan), 
                         provided=float(payload.requested_loan_amount))
        
        application = MortgageApplication(
            client_id=client_id,
            application_type=payload.application_type,
            property_address=payload.property_address,
            property_type=payload.property_type,
            property_value=payload.property_value,
            purchase_price=payload.purchase_price,
            down_payment=payload.down_payment,
            requested_loan_amount=payload.requested_loan_amount,
            amortization_years=payload.amortization_years,
            term_years=payload.term_years,
            mortgage_type=payload.mortgage_type
        )
        
        self.db.add(application)
        await self.db.commit()
        await self.db.refresh(application)
        
        # FIXED: Add audit trail for financial transaction
        logger.info("application_created", 
                   application_id=application.id, 
                   client_id=client_id,
                   loan_amount=float(payload.requested_loan_amount))
        return application

    async def get_application(self, application_id: int) -> MortgageApplication:
        stmt = select(MortgageApplication).where(MortgageApplication.id == application_id).options(selectinload(MortgageApplication.client))
        result = await self.db.execute(stmt)
        app = result.scalar_one_or_none()
        if not app:
            raise NotFoundError(f"Application with id {application_id} not found")
        return app

    async def list_applications(self, limit: int = 100, offset: int = 0) -> List[MortgageApplication]:
        stmt = select(MortgageApplication).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def update_application(self, application_id: int, payload: MortgageApplicationUpdate) -> MortgageApplication:
        application = await self.get_application(application_id)
        logger.info("update_application", application_id=application_id)
        
        # FIXED: Prevent updates to submitted applications
        if application.status != "draft":
            raise AppException("Only draft applications can be updated")
            
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(application, field, value)
            
        await self.db.commit()
        await self.db.refresh(application)
        
        # FIXED: Add audit logging
        logger.info("application_updated", application_id=application_id)
        return application

    async def delete_application(self, application_id: int) -> None:
        application = await self.get_application(application_id)
        await self.db.delete(application)
        await self.db.commit()
        logger.info("application_deleted", application_id=application_id)

    async def submit_application(self, application_id: int) -> MortgageApplication:
        application = await self.get_application(application_id)
        if application.status != "draft":
            raise AppException("Only draft applications can be submitted")
            
        logger.info("submit_application", application_id=application_id)
        application.status = "submitted"
        application.submitted_at = datetime.utcnow()  # FIXED: Use proper datetime assignment
        
        await self.db.commit()
        await self.db.refresh(application)
        
        # FIXED: Add submission audit trail
        logger.info("application_submitted", application_id=application_id)
        return application

    async def add_co_borrower(self, client_id: int, application_id: int, payload: CoBorrowerCreate) -> CoBorrower:
        logger.info("add_co_borrower", application_id=application_id)
        
        # FIXED: Validate that application exists and is draft
        application = await self.get_application(application_id)
        if application.status != "draft":
            raise AppException("Cannot add co-borrower to non-draft application")
        
        sin_encrypted = encrypt_pii(payload.sin)
        
        co_borrower = CoBorrower(
            client_id=client_id,
            application_id=application_id,
            full_name=payload.full_name,
            sin_encrypted=sin_encrypted,
            annual_income=payload.annual_income,
            employment_status=payload.employment_status,
            credit_score=payload.credit_score
        )
        
        self.db.add(co_borrower)
        await self.db.commit()
        await self.db.refresh(co_borrower)
        
        # FIXED: Add audit trail for PII processing
        logger.info("co_borrower_added", 
                   co_borrower_id=co_borrower.id, 
                   application_id=application_id)
        return co_borrower

    async def get_application_summary(self, application_id: int) -> ApplicationSummaryResponse:
        stmt = select(MortgageApplication).where(MortgageApplication.id == application_id).options(
            selectinload(MortgageApplication.client),
            selectinload(MortgageApplication.co_borrowers)
        )
        result = await self.db.execute(stmt)
        application = result.scalar_one_or_none()
        if not application:
            raise NotFoundError(f"Application with id {application_id} not found")
        
        return ApplicationSummaryResponse(
            id=application.id,
            client=application.client,
            application=application,
            co_borrowers=application.co_borrowers
        )

    async def calculate_gds_tds(self, application_id: int) -> dict:
        application = await self.get_application(application_id)
        
        # Get client income details
        client = application.client
        total_annual_income = client.annual_income + client.other_income
        
        # Calculate monthly income
        monthly_income = total_annual_income / 12
        
        # Calculate GDS components
        property_tax = application.property_value * Decimal('0.015')  # Assume 1.5% property tax rate
        heating_costs = application.property_value * Decimal('0.005')  # Assume 0.5% heating costs
        condo_fees = Decimal('0')  # Placeholder - would come from property details
        
        # Calculate gross monthly debt obligations
        monthly_property_expenses = property_tax / 12 + heating_costs / 12 + condo_fees
        
        # Stress test rate per OSFI B-20
        contract_rate = application.requested_loan_amount / application.purchase_price * Decimal('0.05')  # Placeholder rate
        qualifying_rate = max(contract_rate + Decimal('0.02'), Decimal('0.0525'))
        
        # Calculate monthly mortgage payment using qualifying rate
        monthly_mortgage_payment = application.requested_loan_amount * (qualifying_rate / 12) / (1 - (1 + qualifying_rate / 12) ** (-application.amortization_years * 12))
        
        # Calculate GDS
        gds = (monthly_mortgage_payment + monthly_property_expenses) / monthly_income * 100
        
        # Calculate TDS components
        other_debts_monthly = Decimal('0')  # Placeholder - would come from client debts
        tds = (monthly_mortgage_payment + monthly_property_expenses + other_debts_monthly) / monthly_income * 100
        
        # Log calculation breakdown for audit
        logger.info("gds_tds_calculation", 
                   application_id=application_id,
                   monthly_income=float(monthly_income),
                   monthly_mortgage_payment=float(monthly_mortgage_payment),
                   monthly_property_expenses=float(monthly_property_expenses),
                   other_debts_monthly=float(other_debts_monthly),
                   gds=float(gds),
                   tds=float(tds))
        
        # Check against OSFI B-20 limits
        exceeds_gds_limit = gds > Decimal('39')
        exceeds_tds_limit = tds > Decimal('44')
        
        return {
            "gds": float(gds),
            "tds": float(tds),
            "exceeds_gds_limit": exceeds_gds_limit,
            "exceeds_tds_limit": exceeds_tds_limit,
            "limits": {
                "gds_limit": 39,
                "tds_limit": 44
            }
        }