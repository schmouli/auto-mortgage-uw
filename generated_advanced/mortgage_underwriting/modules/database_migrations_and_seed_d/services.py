```python
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
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

class MigrationService:
    """Service for database migrations and seed data operations"""
    
    @staticmethod
    async def hash_password(password: str) -> str:
        return pwd_context.hash(password)
    
    @staticmethod
    async def create_admin_user(db: AsyncSession) -> User:
        """Create the default admin user"""
        admin_exists = await db.execute(
            select(func.count()).select_from(User).where(User.email == "admin@mortgage-uw.local")
        )
        if admin_exists.scalar() == 0:
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
            return admin_user
        return None
    
    @staticmethod
    async def create_broker_user(db: AsyncSession) -> User:
        """Create the default broker user"""
        broker_exists = await db.execute(
            select(func.count()).select_from(User).where(User.email == "broker@mortgage-uw.local")
        )
        if broker_exists.scalar() == 0:
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
            return broker_user
        return None
    
    @staticmethod
    async def create_client_user(db: AsyncSession) -> User:
        """Create the default client user"""
        client_exists = await db.execute(
            select(func.count()).select_from(User).where(User.email == "client@mortgage-uw.local")
        )
        if client_exists.scalar() == 0:
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
            return client_user
        return None
    
    @staticmethod
    async def create_sample_lenders(db: AsyncSession) -> List[Lender]:
        """Create sample lenders (Big 5 banks)"""
        lenders_data = [
            {"name": "RBC", "description": "Royal Bank of Canada"},
            {"name": "TD", "description": "Toronto-Dominion Bank"},
            {"name": "BMO", "description": "Bank of Montreal"},
            {"name": "Scotiabank", "description": "Bank of Nova Scotia"},
            {"name": "CIBC", "description": "Canadian Imperial Bank of Commerce"}
        ]
        
        lenders = []
        for lender_data in lenders_data:
            exists = await db.execute(
                select(func.count()).select_from(Lender).where(Lender.name == lender_data["name"])
            )
            if exists.scalar() == 0:
                lender = Lender(**lender_data, changed_by="system")
                db.add(lender)
                lenders.append(lender)
        
        await db.commit()
        for lender in lenders:
            await db.refresh(lender)
        return lenders
    
    @staticmethod
    async def create_sample_products(db: AsyncSession, lenders: List[Lender]) -> List[Product]:
        """Create 2 products per lender"""
        products = []
        for lender in lenders:
            # Create 5-year fixed product
            fixed_exists = await db.execute(
                select(func.count()).select_from(Product).where(
                    Product.lender_id == lender.id,
                    Product.name == "5-Year Fixed"
                )
            )
            if fixed_exists.scalar() == 0:
                fixed_product = Product(
                    lender_id=lender.id,
                    name="5-Year Fixed",
                    description=f"{lender.name} 5-Year Fixed Rate Mortgage",
                    interest_rate=0.0425,  # 4.25%
                    term_months=60,
                    changed_by="system"
                )
                db.add(fixed_product)
                products.append(fixed_product)
            
            # Create 5-year variable product
            variable_exists = await db.execute(
                select(func.count()).select_from(Product).where(
                    Product.lender_id == lender.id,
                    Product.name == "5-Year Variable"
                )
            )
            if variable_exists.scalar() == 0:
                variable_product = Product(
                    lender_id=lender.id,
                    name="5-Year Variable",
                    description=f"{lender.name} 5-Year Variable Rate Mortgage",
                    interest_rate=0.0375,  # 3.75%
                    term_months=60,
                    changed_by="system"
                )
                db.add(variable_product)
                products.append(variable_product)
        
        await db.commit()
        for product in products:
            await db.refresh(product)
        return products
    
    @staticmethod
    async def create_sample_application(
        db: AsyncSession, 
        client: User, 
        product: Product
    ) -> Application:
        """Create a sample mortgage application"""
        app_exists = await db.execute(
            select(func.count()).select_from(Application).where(
                Application.client_id == client.id
            )
        )
        if app_exists.scalar() == 0:
            application = Application(
                client_id=client.id,
                product_id=product.id,
                status="approved",
                loan_amount=500000.00,
                property_value=750000.00,
                down_payment=150000.00,
                uw_decision="Approved",
                uw_risk_score=750,
                changed_by="system"
            )
            db.add(application)
            await db.commit()
            await db.refresh(application)
            return application
        return None
    
    @staticmethod
    async def create_sample_documents(
        db: AsyncSession, 
        application: Application
    ) -> List[Document]:
        """Create sample documents for the application"""
        doc_types = ["income_verification", "property_appraisal", "credit_report", "identification"]
        documents = []
        
        for i, doc_type in enumerate(doc_types):
            doc_exists = await db.execute(
                select(func.count()).select_from(Document).where(
                    Document.application_id == application.id,
                    Document.document_type == doc_type
                )
            )
            if doc_exists.scalar() == 0:
                document = Document(
                    application_id=application.id,
                    document_type=doc_type,
                    file_path=f"/documents/app_{application.id}/{doc_type}_{i+1}.pdf",
                    file_name=f"{doc_type.replace('_', ' ').title()} {i+1}.pdf",
                    changed_by="system"
                )
                db.add(document)
                documents.append(document)
        
        await db.commit()
        for document in documents:
            await db.refresh(document)
        return documents

class UserService:
    """Service for user operations"""
    
    @staticmethod
    async def get_user(db: AsyncSession, user_id: int) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise UserNotFoundError(f"User with id {user_id} not found")
        return user

class LenderService:
    """Service for lender operations"""
    
    @staticmethod
    async def get_lender(db: AsyncSession, lender_id: int) -> Lender:
        result = await db.execute(select(Lender).where(Lender.id == lender_id))
        lender = result.scalar_one_or_none()
        if not lender:
            raise LenderNotFoundError(f"Lender with id {lender_id} not found")
        return lender

class ProductService:
    """Service for product operations"""
    
    @staticmethod
    async def get_product(db: AsyncSession, product_id: int) -> Product:
        result = await db.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()
        if not product:
            raise ProductNotFoundError(f"Product with id {product_id} not found")
        return product

class ApplicationService:
    """Service for application operations"""
    
    @staticmethod
    async def get_application(db: AsyncSession, application_id: int) -> Application:
        result = await db.execute(select(Application).where(Application.id == application_id))
        application = result.scalar_one_or_none()
        if not application:
            raise ApplicationNotFoundError(f"Application with id {application_id} not found")
        return application
```