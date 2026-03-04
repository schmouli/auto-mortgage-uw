```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
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
            application = await MigrationService.create_sample_application(
                db, client_user, product
            )
            
            # Create documents if application was created
            if application:
                documents = await MigrationService.create_sample_documents(db, application)
        
        return SeedDataResponse(
            message="Database seeded successfully",
            users_created=3 if all([admin, broker, client]) else 0,
            lenders_created=len(lenders),
            products_created=len(products),
            applications_created=1 if application else 0,
            documents_created=len(documents)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Seeding failed: {str(e)}"
        )

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get a user by ID
    """
    try:
        user = await UserService.get_user(db, user_id)
        return user
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.get("/lenders/{lender_id}", response_model=LenderResponse)
async def get_lender(lender_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get a lender by ID
    """
    try:
        lender = await LenderService.get_lender(db, lender_id)
        return lender
    except LenderNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get a product by ID
    """
    try:
        product = await ProductService.get_product(db, product_id)
        return product
    except ProductNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.get("/applications/{application_id}", response_model=ApplicationResponse)
async def get_application(application_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get an application by ID
    """
    try:
        application = await ApplicationService.get_application(db, application_id)
        return application
    except ApplicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
```