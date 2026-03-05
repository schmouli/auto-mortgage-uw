import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from decimal import Decimal
from typing import List, Optional

from mortgage_underwriting.common.security import encrypt_pii
from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.client_intake.models import Client, ClientAddress, MortgageApplication
from mortgage_underwriting.modules.client_intake.schemas import ClientCreate, ClientUpdate, MortgageApplicationCreate, MortgageApplicationUpdate

logger = structlog.get_logger()


class ClientIntakeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_client(self, client_data: ClientCreate) -> Client:
        logger.info("Creating new client", first_name=client_data.first_name, last_name=client_data.last_name)
        
        # Encrypt PII data
        encrypted_dob = encrypt_pii(client_data.date_of_birth)
        encrypted_sin = encrypt_pii(client_data.sin)
        
        try:
            # Create client
            client = Client(
                first_name=client_data.first_name,
                last_name=client_data.last_name,
                email=client_data.email,
                phone=client_data.phone,
                date_of_birth_encrypted=encrypted_dob,
                sin_encrypted=encrypted_sin
            )
            self.db.add(client)
            await self.db.flush()
            
            # Create addresses
            for addr_data in client_data.addresses:
                address = ClientAddress(
                    client_id=client.id,
                    street=addr_data.street,
                    city=addr_data.city,
                    province=addr_data.province,
                    postal_code=addr_data.postal_code,
                    country=addr_data.country,
                    is_primary=addr_data.is_primary
                )
                self.db.add(address)
            
            await self.db.commit()
            await self.db.refresh(client)
            
            logger.info("Client created successfully", client_id=client.id)
            return client
            
        except IntegrityError as e:
            await self.db.rollback()
            logger.error("Failed to create client due to integrity constraint", error=str(e))
            raise AppException("CLIENT_EXISTS", "A client with this email already exists")
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to create client", error=str(e))
            raise AppException("CLIENT_CREATION_FAILED", "Failed to create client")

    async def get_client_by_id(self, client_id: int) -> Optional[Client]:
        logger.info("Fetching client by ID", client_id=client_id)
        stmt = select(Client).where(Client.id == client_id).options(selectinload(Client.addresses), selectinload(Client.applications))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_client(self, client_id: int, client_data: ClientUpdate) -> Optional[Client]:
        logger.info("Updating client", client_id=client_id)
        client = await self.get_client_by_id(client_id)
        if not client:
            return None
            
        # Update client fields
        update_data = client_data.dict(exclude_unset=True, exclude={'addresses'})
        if 'date_of_birth' in update_data:
            update_data['date_of_birth_encrypted'] = encrypt_pii(update_data.pop('date_of_birth'))
        if 'sin' in update_data:
            update_data['sin_encrypted'] = encrypt_pii(update_data.pop('sin'))
            
        for key, value in update_data.items():
            setattr(client, key, value)
            
        # Handle address updates if provided
        if client_data.addresses is not None:
            # Clear existing addresses
            for addr in client.addresses:
                await self.db.delete(addr)
            client.addresses.clear()
            
            # Add new addresses
            for addr_data in client_data.addresses:
                address = ClientAddress(
                    client_id=client.id,
                    street=addr_data.street,
                    city=addr_data.city,
                    province=addr_data.province,
                    postal_code=addr_data.postal_code,
                    country=addr_data.country,
                    is_primary=addr_data.is_primary
                )
                self.db.add(address)
                client.addresses.append(address)
        
        await self.db.commit()
        await self.db.refresh(client)
        logger.info("Client updated successfully", client_id=client.id)
        return client


class MortgageApplicationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_application(self, application_data: MortgageApplicationCreate) -> MortgageApplication:
        logger.info("Creating mortgage application", client_id=application_data.client_id)
        
        # Verify client exists
        stmt = select(Client).where(Client.id == application_data.client_id)
        result = await self.db.execute(stmt)
        client = result.scalar_one_or_none()
        
        if not client:
            logger.warning("Client not found for application", client_id=application_data.client_id)
            raise AppException("CLIENT_NOT_FOUND", "Client not found")
            
        try:
            application = MortgageApplication(**application_data.dict())
            self.db.add(application)
            await self.db.commit()
            await self.db.refresh(application)
            
            logger.info("Mortgage application created", application_id=application.id)
            return application
            
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to create mortgage application", error=str(e))
            raise AppException("APPLICATION_CREATION_FAILED", "Failed to create mortgage application")

    async def get_application_by_id(self, application_id: int) -> Optional[MortgageApplication]:
        logger.info("Fetching mortgage application by ID", application_id=application_id)
        stmt = select(MortgageApplication).where(MortgageApplication.id == application_id).options(selectinload(MortgageApplication.client))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_application(self, application_id: int, application_data: MortgageApplicationUpdate) -> Optional[MortgageApplication]:
        logger.info("Updating mortgage application", application_id=application_id)
        stmt = select(MortgageApplication).where(MortgageApplication.id == application_id)
        result = await self.db.execute(stmt)
        application = result.scalar_one_or_none()
        
        if not application:
            return None
            
        update_data = application_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(application, key, value)
            
        await self.db.commit()
        await self.db.refresh(application)
        logger.info("Mortgage application updated", application_id=application.id)
        return application

    async def calculate_gds_tds(self, application_id: int) -> dict:
        """Calculate GDS and TDS ratios with stress testing per OSFI B-20 guidelines"""
        logger.info("Calculating GDS/TDS", application_id=application_id)
        
        application = await self.get_application_by_id(application_id)
        if not application:
            raise AppException("APPLICATION_NOT_FOUND", "Application not found")
            
        # Get client's total monthly debts (simplified for example)
        # In a real system, you would aggregate all debt obligations
        
        # Calculate qualifying rate per OSFI B-20
        contract_rate = application.interest_rate
        qualifying_rate = max(contract_rate + Decimal('0.02'), Decimal('0.0525'))
        
        # Monthly payment calculation using qualifying rate
        monthly_interest_rate = qualifying_rate / Decimal('12')
        n_payments = application.amortization_period * 12
        
        # Simplified formula for monthly payment
        numerator = monthly_interest_rate * (1 + monthly_interest_rate) ** n_payments
        denominator = ((1 + monthly_interest_rate) ** n_payments) - 1
        monthly_payment = application.loan_amount * (numerator / denominator)
        
        # GDS calculation (housing costs / gross income)
        # Assuming annual gross income is stored somewhere (simplified here)
        annual_income = Decimal('100000')  # Placeholder - should come from client data
        gross_monthly_income = annual_income / Decimal('12')
        
        # Housing costs (monthly payment + property taxes + heating + condo fees)
        property_taxes = application.property_value * Decimal('0.015') / Decimal('12')  # Estimate
        heating_costs = Decimal('200')  # Estimate
        condo_fees = Decimal('300')  # Estimate
        
        housing_costs = monthly_payment + property_taxes + heating_costs + condo_fees
        gds_ratio = (housing_costs / gross_monthly_income) * Decimal('100')
        
        # TDS calculation (total debt payments / gross income)
        other_debts = Decimal('500')  # Estimate - should come from client's debt summary
        total_monthly_debt = housing_costs + other_debts
        tds_ratio = (total_monthly_debt / gross_monthly_income) * Decimal('100')
        
        # Audit logging
        logger.info(
            "GDS/TDS calculation breakdown",
            application_id=application_id,
            contract_rate=float(contract_rate),
            qualifying_rate=float(qualifying_rate),
            monthly_payment=float(monthly_payment),
            gross_monthly_income=float(gross_monthly_income),
            housing_costs=float(housing_costs),
            other_debts=float(other_debts),
            gds_ratio=float(gds_ratio),
            tds_ratio=float(tds_ratio)
        )
        
        # Check compliance with OSFI B-20 limits
        gds_compliant = gds_ratio <= Decimal('39')
        tds_compliant = tds_ratio <= Decimal('44')
        
        return {
            "application_id": application_id,
            "gds_ratio": float(gds_ratio),
            "tds_ratio": float(tds_ratio),
            "gds_compliant": gds_compliant,
            "tds_compliant": tds_compliant,
            "breakdown": {
                "contract_rate": float(contract_rate),
                "qualifying_rate": float(qualifying_rate),
                "monthly_payment": float(monthly_payment),
                "gross_monthly_income": float(gross_monthly_income),
                "housing_costs": float(housing_costs),
                "other_debts": float(other_debts)
            }
        }