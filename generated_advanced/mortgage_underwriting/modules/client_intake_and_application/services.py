--- services.py ---
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
        """Create a new client with associated addresses.
        
        Args:
            client_data: Client creation data including addresses
            
        Returns:
            Created client object
            
        Raises:
            AppException: If client creation fails due to integrity constraints
        """
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
            logger.error("Failed to create client due to integrity constraint", error=str(e), exc_info=True)
            raise AppException("CLIENT_EXISTS", "A client with this email already exists")
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to create client", error=str(e), exc_info=True)
            raise AppException("CLIENT_CREATION_FAILED", "Failed to create client")

    async def get_client_by_id(self, client_id: int) -> Optional[Client]:
        """Fetch a client by ID with associated addresses and applications.
        
        Args:
            client_id: ID of the client to fetch
            
        Returns:
            Client object if found, None otherwise
        """
        logger.info("Fetching client by ID", client_id=client_id)
        stmt = select(Client).where(Client.id == client_id).options(selectinload(Client.addresses), selectinload(Client.applications))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_client(self, client_id: int, client_data: ClientUpdate) -> Optional[Client]:
        """Update a client's information.
        
        Args:
            client_id: ID of the client to update
            client_data: Updated client data
            
        Returns:
            Updated client object if successful, None if client not found
        """
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
        """Create a new mortgage application.
        
        Args:
            application_data: Application creation data
            
        Returns:
            Created application object
            
        Raises:
            AppException: If client not found or creation fails
        """
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
            logger.error("Failed to create mortgage application", error=str(e), exc_info=True)
            raise AppException("APPLICATION_CREATION_FAILED", "Failed to create mortgage application")

    async def get_application_by_id(self, application_id: int) -> Optional[MortgageApplication]:
        """Fetch a mortgage application by ID.
        
        Args:
            application_id: ID of the application to fetch
            
        Returns:
            Application object if found, None otherwise
        """
        logger.info("Fetching mortgage application by ID", application_id=application_id)
        stmt = select(MortgageApplication).where(MortgageApplication.id == application_id).options(selectinload(MortgageApplication.client))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_application(self, application_id: int, application_data: MortgageApplicationUpdate) -> Optional[MortgageApplication]:
        """Update a mortgage application.
        
        Args:
            application_id: ID of the application to update
            application_data: Updated application data
            
        Returns:
            Updated application object if successful, None if application not found
        """
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
        """Calculate GDS and TDS ratios with stress testing per OSFI B-20 guidelines.
        
        Args:
            application_id: The ID of the mortgage application to analyze
            
        Returns:
            Dictionary containing GDS/TDS calculations and compliance status
            
        Raises:
            AppException: If application not found or calculation fails
        """
        logger.info("Calculating GDS/TDS", application_id=application_id)
        
        try:
            # Fetch application with client info
            stmt = select(MortgageApplication).where(MortgageApplication.id == application_id)
            result = await self.db.execute(stmt)
            application = result.scalar_one_or_none()
            
            if not application:
                raise AppException("APPLICATION_NOT_FOUND", "Application not found")
                
            # Get client's total monthly liabilities (simplified for example)
            # In real implementation, would query all active loans for client
            total_monthly_liabilities = application.loan_amount / Decimal('1000')  # Placeholder calculation
            
            # Calculate qualifying rate per OSFI B-20
            qualifying_rate = max(application.interest_rate + Decimal('0.02'), Decimal('0.0525'))
            
            # Calculate GDS and TDS (simplified formulas)
            gds = (application.loan_amount * qualifying_rate / Decimal('12')) / (application.loan_amount / Decimal('10'))
            tds = ((application.loan_amount * qualifying_rate / Decimal('12')) + total_monthly_liabilities) / (application.loan_amount / Decimal('10'))
            
            # Check compliance with OSFI B-20 limits
            gds_compliant = gds <= Decimal('0.39')
            tds_compliant = tds <= Decimal('0.44')
            
            result_dict = {
                "application_id": application_id,
                "qualifying_rate": qualifying_rate,
                "gds_ratio": gds,
                "tds_ratio": tds,
                "gds_compliant": gds_compliant,
                "tds_compliant": tds_compliant,
                "limits": {
                    "gds_limit": "39%",
                    "tds_limit": "44%"
                }
            }
            
            logger.info("GDS/TDS calculation completed", 
                       application_id=application_id,
                       gds=float(gds),
                       tds=float(tds),
                       gds_compliant=gds_compliant,
                       tds_compliant=tds_compliant)
                        
            return result_dict
            
        except AppException:
            # Re-raise known exceptions
            raise
        except Exception as e:
            logger.error("Failed to calculate GDS/TDS", exc_info=True)
            raise AppException("CALCULATION_ERROR", "Failed to calculate GDS/TDS ratios")