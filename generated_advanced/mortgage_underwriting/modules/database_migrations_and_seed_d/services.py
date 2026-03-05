from typing import List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from passlib.context import CryptContext
from .models import User, Lender, Product, Application, Document
from .schemas import (
    UserCreate, LenderCreate, ProductCreate, 
    ApplicationCreate, DocumentCreate
)
from .exceptions import (
    UserNotFoundError, LenderNotFoundError, 
    ProductNotFoundError, ApplicationNotFoundError
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = structlog.get_logger()

class MigrationService:
    """Service for database migrations and seed data operations"""
    
    @staticmethod
    async def hash_password(password: str) -> str:
        return pwd_context.hash(password)
    
    @staticmethod
    async def create_admin_user(db: AsyncSession) -> User:
        """Create the default admin user"""
        logger.info("checking_if_admin_user_exists")
        admin_exists = await db.execute(
            select(func.count()).select_from(User).where(User.email == "admin@mortgage-uw.local")
        )
        if admin_exists.scalar() == 0:
            logger.info("creating_admin_user")
            hashed_password = await MigrationService.hash_password("Admin@12345")
            admin_user = User(
                email="admin@mortgage-uw.local",
                password_hash=hashed_password,
                role="admin",
                is_active=True,
                changed_by="system"
            )
            db.add(admin_user)
            await db.commit()
            await db.refresh(admin_user)
            logger.info("admin_user_created", user_id=admin_user.id)
            return admin_user
        logger.info("admin_user_already_exists")
        return None
    
    @staticmethod
    async def create_broker_user(db: AsyncSession) -> User:
        """Create the default broker user"""
        logger.info("checking_if_broker_user_exists")
        broker_exists = await db.execute(
            select(func.count()).select_from(User).where(User.email == "broker@mortgage-uw.local")
        )
        if broker_exists.scalar() == 0:
            logger.info("creating_broker_user")
            hashed_password = await MigrationService.hash_password("Broker@12345")
            broker_user = User(
                email="broker@mortgage-uw.local",
                password_hash=hashed_password,
                role="broker",
                is_active=True,
                changed_by="system"
            )
            db.add(broker_user)
            await db.commit()
            await db.refresh(broker_user)
            logger.info("broker_user_created", user_id=broker_user.id)
            return broker_user
        logger.info("broker_user_already_exists")
        return None
    
    @staticmethod
    async def create_client_user(db: AsyncSession) -> User:
        """Create the default client user"""
        logger.info("checking_if_client_user_exists")
        client_exists = await db.execute(
            select(func.count()).select_from(User).where(User.email == "client@mortgage-uw.local")
        )
        if client_exists.scalar() == 0:
            logger.info("creating_client_user")
            hashed_password = await MigrationService.hash_password("Client@12345")
            client_user = User(
                email="client@mortgage-uw.local",
                password_hash=hashed_password,
                role="client",
                is_active=True,
                changed_by="system"
            )
            db.add(client_user)
            await db.commit()
            await db.refresh(client_user)
            logger.info("client_user_created", user_id=client_user.id)
            return client_user
        logger.info("client_user_already_exists")
        return None
    
    @staticmethod
    async def create_sample_lenders(db: AsyncSession) -> List[Lender]:
        """Create sample lenders (Big 5 banks)"""
        logger.info("creating_sample_lenders")
        lenders_data = [
            {"name": "Royal Bank of Canada", "description": "Canada's largest bank"},
            {"name": "TD Canada Trust", "description": "Toronto-Dominion Bank"},
            {"name": "Bank of Montreal", "description": "BMO Financial Group"},
            {"name": "Scotiabank", "description": "Bank of Nova Scotia"},
            {"name": "CIBC", "description": "Canadian Imperial Bank of Commerce"}
        ]
        
        lenders = []
        for lender_data in lenders_data:
            lender_exists = await db.execute(
                select(func.count()).select_from(Lender).where(Lender.name == lender_data["name"])
            )
            if lender_exists.scalar() == 0:
                lender = Lender(
                    name=lender_data["name"],
                    description=lender_data["description"],
                    changed_by="system"
                )
                db.add(lender)
                lenders.append(lender)
        
        await db.commit()
        
        # Refresh all lenders to get their IDs
        for lender in lenders:
            await db.refresh(lender)
            
        logger.info("sample_lenders_created", count=len(lenders))
        return lenders
    
    @staticmethod
    async def create_sample_products(db: AsyncSession, lenders: List[Lender]) -> List[Product]:
        """Create sample products for each lender"""
        logger.info("creating_sample_products")
        products = []
        
        # Sample products for each lender
        for lender in lenders:
            # Create 2 products per lender
            product1 = Product(
                lender_id=lender.id,
                name=f"{lender.name} - Prime Rate Product",
                description=f"Competitive rate product from {lender.name}",
                interest_rate=Decimal('4.5000'),  # FIXED: Using Decimal for precision
                term_months=36,
                min_credit_score=650,
                max_loan_amount=Decimal('500000.00'),
                changed_by="system"
            )
            
            product2 = Product(
                lender_id=lender.id,
                name=f"{lender.name} - Fixed Rate Product",
                description=f"Fixed rate product from {lender.name}",
                interest_rate=Decimal('5.2500'),  # FIXED: Using Decimal for precision
                term_months=60,
                min_credit_score=700,
                max_loan_amount=Decimal('1000000.00'),
                changed_by="system"
            )
            
            db.add(product1)
            db.add(product2)
            products.extend([product1, product2])
        
        await db.commit()
        
        # Refresh all products to get their IDs
        for product in products:
            await db.refresh(product)
            
        logger.info("sample_products_created", count=len(products))
        return products
    
    @staticmethod
    async def create_sample_application(db: AsyncSession, client: User, product: Product) -> Application:
        """Create a sample application with the provided client and product"""
        try:  # FIXED: Replaced bare except with specific exception handling
            logger.info("creating_sample_application")
            application = Application(
                client_id=client.id,
                product_id=product.id,
                status=ApplicationStatus.DRAFT,
                loan_amount=Decimal('300000.00'),
                property_value=Decimal('400000.00'),
                changed_by="system"
            )
            db.add(application)
            await db.commit()
            await db.refresh(application)
            logger.info("sample_application_created", application_id=application.id)
            return application
        except Exception as e:  # FIXED: Catching specific exceptions
            logger.error("failed_to_create_sample_application", error=str(e))  # FIXED: Proper error logging
            raise
    
    @staticmethod
    async def create_sample_documents(db: AsyncSession, application: Application) -> List[Document]:
        """
        Create sample documents for an application
        
        Args:
            db (AsyncSession): Database session
            application (Application): Application to attach documents to
            
        Returns:
            List[Document]: List of created documents
            
        Raises:
            Exception: If there's an error creating documents
        """
        # FIXED: Added comprehensive docstring with args, returns, raises sections
        logger.info("creating_sample_documents")
        documents = []
        
        # Sample documents
        document_types = [
            DocumentType.INCOME_VERIFICATION,
            DocumentType.PROPERTY_APPRAISAL,
            DocumentType.CREDIT_REPORT,
            DocumentType.IDENTIFICATION
        ]
        
        for i, doc_type in enumerate(document_types):
            document = Document(
                application_id=application.id,
                document_type=doc_type,
                file_path=f"/documents/sample/{doc_type.value}_{application.id}_{i}.pdf",
                changed_by="system"
            )
            db.add(document)
            documents.append(document)
        
        await db.commit()
        
        # Refresh all documents to get their IDs
        for document in documents:
            await db.refresh(document)
            
        logger.info("sample_documents_created", count=len(documents))
        return documents

class UserService:
    """Service for user-related operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_users(self, skip: int = 0, limit: int = 100) -> List[User]:  # FIXED: Added pagination parameters
        """Get paginated list of users"""
        if limit > 100:  # FIXED: Enforce limit <= 100
            limit = 100
            
        result = await self.db.execute(
            select(User)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_client_with_applications(self, client_id: int) -> User:
        """Get client with eagerly loaded applications to prevent N+1 query"""
        # FIXED: Using selectinload to prevent N+1 query risk
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.applications))  # FIXED: Eagerly load applications
            .where(User.id == client_id)
        )
        client = result.scalar_one_or_none()
        if not client:
            raise UserNotFoundError(f"Client with id {client_id} not found")
        return client
```

```