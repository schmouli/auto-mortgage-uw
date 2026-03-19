from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.common.security import encrypt_pii
from mortgage_underwriting.modules.client_intake.models import Client, Application, CoBorrower
from mortgage_underwriting.modules.client_intake.schemas import (
    ClientCreate,
    ClientUpdate,
    ApplicationCreate,
    ApplicationUpdate,
    CoBorrowerCreate,
    PropertyAddressDB
)

logger = structlog.get_logger()

class ClientIntakeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_client(self, payload: ClientCreate, user_id: int) -> Client:
        logger.info("create_client", user_id=user_id)
        
        # Encrypt PII
        sin_encrypted = encrypt_pii(payload.sin)
        dob_encrypted = encrypt_pii(payload.date_of_birth.isoformat())
        
        client_dict = payload.model_dump(exclude={'sin', 'date_of_birth'})
        client_dict['sin_encrypted'] = sin_encrypted
        client_dict['date_of_birth_encrypted'] = dob_encrypted
        client_dict['user_id'] = user_id
        
        client = Client(**client_dict)
        self.db.add(client)
        await self.db.commit()
        await self.db.refresh(client)
        
        logger.info("client_created", client_id=client.id)
        return client

    async def update_client(self, client_id: int, payload: ClientUpdate) -> Client:
        logger.info("update_client", client_id=client_id)
        
        result = await self.db.execute(select(Client).where(Client.id == client_id))
        client = result.scalar_one_or_none()
        
        if not client:
            raise NotFoundError(f"Client with id {client_id} not found")
            
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(client, key, value)
            
        await self.db.commit()
        await self.db.refresh(client)
        
        logger.info("client_updated", client_id=client.id)
        return client

    async def get_client(self, client_id: int) -> Client:
        logger.info("get_client", client_id=client_id)
        
        result = await self.db.execute(select(Client).where(Client.id == client_id))
        client = result.scalar_one_or_none()
        
        if not client:
            raise NotFoundError(f"Client with id {client_id} not found")
            
        return client

    async def create_application(self, payload: ApplicationCreate) -> Application:
        logger.info("create_application", client_id=payload.client_id)
        
        # Validate client exists
        result = await self.db.execute(select(Client).where(Client.id == payload.client_id))
        client = result.scalar_one_or_none()
        
        if not client:
            raise AppException("Invalid client_id provided")
            
        # Business rule validation: Check down payment minimums
        if payload.application_type == 'purchase' and payload.down_payment:
            down_payment_percent = (payload.down_payment / payload.purchase_price) * 100
            if down_payment_percent < 5:
                raise AppException("Minimum down payment for purchase must be at least 5%")
            
        # Create application
        app_dict = payload.model_dump(exclude={'co_borrowers'})
        app_dict['property_address'] = app_dict['property_address'].model_dump()
        
        application = Application(**app_dict)
        self.db.add(application)
        await self.db.flush()  # Get application.id without committing
        
        # Create co-borrowers if provided
        if payload.co_borrowers:
            for co_borrower_data in payload.co_borrowers:
                # Encrypt SIN and DOB
                sin_encrypted = encrypt_pii(co_borrower_data.sin)
                dob_encrypted = encrypt_pii(co_borrower_data.date_of_birth.isoformat())
                
                co_borrower_dict = co_borrower_data.model_dump(exclude={'sin', 'date_of_birth'})
                co_borrower_dict['sin_encrypted'] = sin_encrypted
                co_borrower_dict['date_of_birth_encrypted'] = dob_encrypted
                co_borrower_dict['application_id'] = application.id
                
                co_borrower = CoBorrower(**co_borrower_dict)
                self.db.add(co_borrower)
                
        await self.db.commit()
        await self.db.refresh(application)
        
        # Load relationships
        result = await self.db.execute(
            select(Application)
            .options(selectinload(Application.co_borrowers))
            .where(Application.id == application.id)
        )
        application = result.scalar_one()
        
        logger.info("application_created", application_id=application.id)
        return application

    async def get_application(self, application_id: int) -> Application:
        logger.info("get_application", application_id=application_id)
        
        result = await self.db.execute(
            select(Application)
            .options(selectinload(Application.co_borrowers))
            .where(Application.id == application_id)
        )
        application = result.scalar_one_or_none()
        
        if not application:
            raise NotFoundError(f"Application with id {application_id} not found")
            
        return application

    async def update_application(self, application_id: int, payload: ApplicationUpdate) -> Application:
        logger.info("update_application", application_id=application_id)
        
        result = await self.db.execute(
            select(Application)
            .options(selectinload(Application.co_borrowers))
            .where(Application.id == application_id)
        )
        application = result.scalar_one_or_none()
        
        if not application:
            raise NotFoundError(f"Application with id {application_id} not found")
            
        # Update fields
        update_data = payload.model_dump(exclude_unset=True)
        if 'property_address' in update_data:
            update_data['property_address'] = update_data['property_address'].model_dump()
            
        for key, value in update_data.items():
            setattr(application, key, value)
            
        await self.db.commit()
        await self.db.refresh(application)
        
        logger.info("application_updated", application_id=application.id)
        return application

    async def submit_application(self, application_id: int) -> Application:
        logger.info("submit_application", application_id=application_id)
        
        result = await self.db.execute(
            select(Application)
            .options(selectinload(Application.co_borrowers))
            .where(Application.id == application_id)
        )
        application = result.scalar_one_or_none()
        
        if not application:
            raise NotFoundError(f"Application with id {application_id} not found")
            
        if application.status != "draft":
            raise AppException("Only draft applications can be submitted")
            
        application.status = "submitted"
        application.submitted_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(application)
        
        logger.info("application_submitted", application_id=application.id)
        return application

    async def list_applications(
        self, 
        client_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Application]:
        logger.info("list_applications", client_id=client_id, status=status)
        
        query = select(Application)
        
        if client_id:
            query = query.where(Application.client_id == client_id)
        if status:
            query = query.where(Application.status == status)
            
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        applications = result.scalars().all()
        
        return applications

    async def get_application_summary(self, application_id: int) -> Dict[str, Any]:
        logger.info("get_application_summary", application_id=application_id)
        
        result = await self.db.execute(
            select(Application)
            .join(Client)
            .options(selectinload(Application.co_borrowers))
            .where(Application.id == application_id)
        )
        application = result.scalar_one_or_none()
        
        if not application:
            raise NotFoundError(f"Application with id {application_id} not found")
            
        # Get client information
        client_result = await self.db.execute(select(Client).where(Client.id == application.client_id))
        client = client_result.scalar_one_or_none()
        
        if not client:
            raise NotFoundError(f"Client for application {application_id} not found")
        
        # Create summary data
        summary = {
            "id": application.id,
            "client_full_name": f"Client {client.id}",  # In a real implementation, this would come from User table
            "property_address": PropertyAddressDB(**application.property_address),
            "property_value": application.property_value,
            "requested_loan_amount": application.requested_loan_amount,
            "status": application.status,
            "created_at": application.created_at,
            "submitted_at": application.submitted_at
        }
        
        return summary