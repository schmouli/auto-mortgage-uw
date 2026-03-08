from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog
from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.common.security import encrypt_pii
from mortgage_underwriting.modules.intake.models import Client, MortgageApplication, CoBorrower
from mortgage_underwriting.modules.intake.schemas import (
    ClientCreate,
    ClientUpdate,
    ApplicationCreate,
    ApplicationUpdate,
    CoBorrowerCreate
)

logger = structlog.get_logger()


class IntakeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_client(self, user_id: int, payload: ClientCreate) -> Client:
        logger.info("create_client", user_id=user_id)
        
        # Encrypt PII
        sin_encrypted: str = encrypt_pii(payload.sin)
        dob_encrypted: str = encrypt_pii(payload.date_of_birth)
        
        client = Client(
            user_id=user_id,
            sin_encrypted=sin_encrypted,
            date_of_birth=dob_encrypted,
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
        return client

    async def update_client(self, client_id: int, payload: ClientUpdate) -> Client:
        logger.info("update_client", client_id=client_id)
        
        client = await self.db.get(Client, client_id)
        if not client:
            raise NotFoundError(f"Client with id {client_id} not found")
            
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(client, field, value)
            
        await self.db.commit()
        await self.db.refresh(client)
        return client

    async def create_application(self, user_role: str, user_id: int, payload: ApplicationCreate) -> MortgageApplication:
        logger.info("create_application", user_role=user_role, user_id=user_id)
        
        # Determine client_id
        if user_role == "client":
            client_result = await self.db.execute(select(Client).where(Client.user_id == user_id))
            client = client_result.scalar_one_or_none()
            if not client:
                raise AppException("Client profile not found")
            client_id = client.id
        elif user_role == "broker":
            if not payload.client_id:
                raise AppException("client_id is required for broker-created applications")
            client_id = payload.client_id
        else:
            raise AppException("Invalid user role")
            
        # Encrypt property address
        property_address_encrypted: str = encrypt_pii(payload.property_address)
        
        # Create application
        app = MortgageApplication(
            client_id=client_id,
            broker_id=user_id if user_role == "broker" else None,
            application_type=payload.application_type,
            property_address=property_address_encrypted,
            property_type=payload.property_type,
            property_value=payload.property_value,
            purchase_price=payload.purchase_price,
            down_payment=payload.down_payment,
            requested_loan_amount=payload.requested_loan_amount,
            amortization_years=payload.amortization_years,
            term_years=payload.term_years,
            mortgage_type=payload.mortgage_type
        )
        
        # Calculate LTV and insurance
        await self._calculate_ltv_and_insurance(app)
        
        self.db.add(app)
        await self.db.commit()
        await self.db.refresh(app)
        
        # Handle co-borrowers
        if payload.co_borrowers:
            for co_borrower_data in payload.co_borrowers:
                sin_encrypted: str = encrypt_pii(co_borrower_data.sin)
                co_borrower = CoBorrower(
                    application_id=app.id,
                    full_name=co_borrower_data.full_name,
                    sin_encrypted=sin_encrypted,
                    annual_income=co_borrower_data.annual_income,
                    employment_status=co_borrower_data.employment_status,
                    credit_score=co_borrower_data.credit_score
                )
                self.db.add(co_borrower)
            await self.db.commit()
            
        return app

    async def update_application(self, application_id: int, payload: ApplicationUpdate) -> MortgageApplication:
        logger.info("update_application", application_id=application_id)
        
        app = await self.db.get(MortgageApplication, application_id)
        if not app:
            raise NotFoundError(f"Application with id {application_id} not found")
            
        # Update fields
        update_data: Dict[str, Any] = payload.model_dump(exclude_unset=True)
        if 'property_address' in update_data:
            update_data['property_address'] = encrypt_pii(update_data['property_address'])
            
        for field, value in update_data.items():
            setattr(app, field, value)
            
        # Recalculate LTV and insurance
        await self._calculate_ltv_and_insurance(app)
        
        await self.db.commit()
        await self.db.refresh(app)
        return app

    async def submit_application(self, application_id: int) -> MortgageApplication:
        logger.info("submit_application", application_id=application_id)
        
        app = await self.db.get(MortgageApplication, application_id)
        if not app:
            raise NotFoundError(f"Application with id {application_id} not found")
            
        if app.status != "draft":
            raise AppException("Only draft applications can be submitted")
            
        app.status = "submitted"
        # In a real system, we'd set submitted_at here
        
        await self.db.commit()
        await self.db.refresh(app)
        return app

    async def get_application_summary(self, application_id: int) -> Dict[str, Any]:
        logger.info("get_application_summary", application_id=application_id)
        
        # Load application with relationships
        result = await self.db.execute(
            select(MortgageApplication)
            .options(selectinload(MortgageApplication.client).selectinload(Client.user))
            .options(selectinload(MortgageApplication.co_borrowers))
            .where(MortgageApplication.id == application_id)
        )
        app = result.scalar_one_or_none()
        if not app:
            raise NotFoundError(f"Application with id {application_id} not found")
            
        # Calculate totals
        total_income: Decimal = app.client.annual_income + app.client.other_income
        for cb in app.co_borrowers:
            total_income += cb.annual_income
            
        # Placeholder calculations - would integrate with debt service calculators
        gds_ratio: Decimal = Decimal('0.30')  # 30%
        tds_ratio: Decimal = Decimal('0.40')  # 40%
        qualifying_rate: Decimal = max(Decimal('0.0525'), Decimal('0.02') + Decimal('0.0325'))  # 5.25%
        
        return {
            "id": app.id,
            "client_name": app.client.user.full_name,
            "property_address": app.property_address,  # Would decrypt in real impl
            "total_income": total_income,
            "gds_ratio": gds_ratio,
            "tds_ratio": tds_ratio,
            "qualifying_rate": qualifying_rate,
            "ltv_ratio": app.ltv_ratio,
            "insurance_required": app.insurance_required,
            "cmhc_premium_rate": app.cmhc_premium_rate
        }

    async def _calculate_ltv_and_insurance(self, app: MortgageApplication) -> None:
        """Calculate LTV ratio and determine insurance requirements per CMHC guidelines."""
        # Determine property value for LTV calculation
        property_value_for_ltv = app.property_value if app.property_value else app.purchase_price
        if not property_value_for_ltv or not app.requested_loan_amount:
            logger.warning("insufficient_data_for_ltv", application_id=app.id)
            return
            
        try:
            ltv_ratio_decimal = app.requested_loan_amount / property_value_for_ltv
            app.ltv_ratio = ltv_ratio_decimal.quantize(Decimal('0.0001'))
            
            # CMHC insurance logic
            if ltv_ratio_decimal > Decimal('0.80'):
                app.insurance_required = True
                # Premium tiers based on LTV percentage
                ltv_percent = ltv_ratio_decimal * 100
                if Decimal('80.01') <= ltv_percent <= Decimal('85.00'):
                    app.cmhc_premium_rate = Decimal('0.0280')
                elif Decimal('85.01') <= ltv_percent <= Decimal('90.00'):
                    app.cmhc_premium_rate = Decimal('0.0310')
                elif Decimal('90.01') <= ltv_percent <= Decimal('95.00'):
                    app.cmhc_premium_rate = Decimal('0.0400')
                else:
                    logger.warning("high_ltv_no_insurance_tier", ltv_percent=float(ltv_percent))
                    app.cmhc_premium_rate = None  # No standard tier available
            else:
                app.insurance_required = False
                app.cmhc_premium_rate = None
                
        except Exception as e:
            logger.error("ltv_calculation_error", error=str(e), application_id=app.id)
            raise AppException("Failed to calculate LTV ratio")