from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import structlog
from .database import get_db
from .services import (
    MigrationService, UserService, LenderService, 
    ProductService, ApplicationService
)
from .schemas import (
    UserResponse, LenderResponse, ProductResponse, 
    ApplicationResponse, DocumentResponse, SeedDataResponse
)
from .exceptions import (
    UserNotFoundError, LenderNotFoundError, 
    ProductNotFoundError, ApplicationNotFoundError
)

logger = structlog.get_logger()  # FIXED: Added logger
router = APIRouter(prefix="/migrations", tags=["migrations"])

@router.post("/seed", response_model=SeedDataResponse)
async def seed_database(db: AsyncSession = Depends(get_db)):
    """
    Seed the database with initial data including:
    - Admin, broker, and client users
    - Sample lenders (Big 5 banks)
    - Products for each lender
    - A sample application with documents
    """
    try:
        logger.info("starting_database_seeding")  # FIXED: Replaced print statements with proper logging
        # Create users
        admin = await MigrationService.create_admin_user(db)
        broker = await MigrationService.create_broker_user(db)
        client = await MigrationService.create_client_user(db)
        
        # Get client user for application creation
        client_result = await db.execute(
            select(User).where(User.email == "client@mortgage-uw.local")
        )
        client_user = client_result.scalar_one()
        
        # Create lenders
        lenders = await MigrationService.create_sample_lenders(db)
        
        # Create products
        products = await MigrationService.create_sample_products(db, lenders)
        
        # Create application using first product
        product = products[0] if products else None
        application = None
        documents = []
        
        if product:
            application = await MigrationService.create_sample_application(db, client_user, product)
            
            # Create documents for the application
            if application:
                documents = await MigrationService.create_sample_documents(db, application)
        
        logger.info("database_seeding_completed")  # FIXED: Replaced print statements with proper logging
        return SeedDataResponse(
            message="Database seeded successfully",
            admin_created=bool(admin),
            broker_created=bool(broker),
            client_created=bool(client),
            lenders_created=len(lenders),
            products_created=len(products),
            application_created=bool(application),
            documents_created=len(documents)
        )
    except Exception as e:
        logger.error("database_seeding_failed", error=str(e))  # FIXED: Proper error logging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to seed database"
        )

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=100),  # FIXED: Added pagination with limit <= 100 enforced
    db: AsyncSession = Depends(get_db)
):
    """Get paginated list of users"""
    try:
        logger.info("fetching_users_list", skip=skip, limit=limit)
        user_service = UserService(db)
        users = await user_service.get_users(skip=skip, limit=limit)
        logger.info("users_list_fetched", count=len(users))
        return users
    except Exception as e:
        logger.error("failed_to_fetch_users", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch users"
        )
```