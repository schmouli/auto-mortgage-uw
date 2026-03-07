from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
import json

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.modules.admin_panel.models import AuditLog, Lender, Product
from mortgage_underwriting.modules.admin_panel.schemas import (
    AuditLogCreate,
    AuditLogResponse,
    AdminUserListQuery,
    AdminUserResponse,
    LenderCreate,
    LenderUpdate,
    LenderResponse,
    ProductCreate,
    ProductUpdate,
    ProductResponse,
)
from mortgage_underwriting.modules.auth.models import User

logger = structlog.get_logger()


class AuditLogService:
    """Immutable audit log service - append-only."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, payload: AuditLogCreate) -> AuditLogResponse:
        """Create a new audit log entry (immutable).

        Args:
            payload: Audit log creation schema

        Returns:
            Created audit log response

        Raises:
            AppException: If database error occurs
        """
        logger.info(
            "audit_log_create",
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            action=payload.action,
        )

        try:
            instance = AuditLog(
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                action=payload.action,
                changed_by=payload.changed_by,
                old_values=payload.old_values,
                new_values=payload.new_values,
                ip_address=payload.ip_address,
                user_agent=payload.user_agent,
            )
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            return AuditLogResponse.model_validate(instance)
        except Exception as e:
            await self.db.rollback()
            logger.error("audit_log_create_failed", error=str(e))
            raise AppException(f"Failed to create audit log: {str(e)}") from e

    async def list_logs(self, page: int = 1, limit: int = 50) -> Dict[str, Any]:
        """List audit logs with pagination.
        
        Args:
            page: Page number (1-indexed)
            limit: Items per page
            
        Returns:
            Dict containing logs and pagination info
        """
        offset = (page - 1) * limit
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        logs = result.scalars().all()
        count_stmt = select(func.count()).select_from(AuditLog)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()
        return {
            "logs": [AuditLogResponse.model_validate(log) for log in logs],
            "total": total,
            "page": page,
            "limit": limit,
        }


class UserService:
    """Service for managing users."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_users(self, query: AdminUserListQuery) -> Dict[str, Any]:
        """List users with filters and pagination.
        
        Args:
            query: Query parameters for filtering users
            
        Returns:
            Dict containing users and pagination info
        """
        offset = (query.page - 1) * query.limit
        stmt = select(User)
        if query.role:
            stmt = stmt.where(User.role == query.role)
        if query.is_active is not None:
            stmt = stmt.where(User.is_active == query.is_active)
        stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(query.limit)
        result = await self.db.execute(stmt)
        users = result.scalars().all()
        count_stmt = select(func.count()).select_from(User)
        if query.role:
            count_stmt = count_stmt.where(User.role == query.role)
        if query.is_active is not None:
            count_stmt = count_stmt.where(User.is_active == query.is_active)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()
        return {
            "users": [AdminUserResponse.model_validate(user) for user in users],
            "total": total,
            "page": query.page,
            "limit": query.limit,
        }

    async def deactivate_user(self, user_id: int, reason: str) -> AdminUserResponse:
        """Deactivate a user.
        
        Args:
            user_id: ID of user to deactivate
            reason: Reason for deactivation
            
        Returns:
            Updated user response
            
        Raises:
            NotFoundError: If user doesn't exist
        """
        # FIXED: Add input validation
        if not isinstance(user_id, int) or user_id <= 0:
            raise AppException("Invalid user ID")
        if not reason or not isinstance(reason, str):
            raise AppException("Reason is required")
            
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError(f"User with ID {user_id} not found")
        user.is_active = False
        await self.db.commit()
        await self.db.refresh(user)
        logger.info("user_deactivated", user_id=user_id, reason=reason)
        
        # FIXED: Create audit log for user deactivation
        audit_service = AuditLogService(self.db)
        await audit_service.create(AuditLogCreate(
            entity_type="users",
            entity_id=user_id,
            action="UPDATE",
            reason=f"User deactivated: {reason}",
            old_values=json.dumps({"is_active": True}),
            new_values=json.dumps({"is_active": False})
        ))
        
        return AdminUserResponse.model_validate(user)

    async def update_user_role(self, user_id: int, new_role: str) -> AdminUserResponse:
        """Update a user's role.
        
        Args:
            user_id: ID of user to update
            new_role: New role to assign
            
        Returns:
            Updated user response
            
        Raises:
            NotFoundError: If user doesn't exist
        """
        # FIXED: Add input validation
        if not isinstance(user_id, int) or user_id <= 0:
            raise AppException("Invalid user ID")
        if not new_role or not isinstance(new_role, str):
            raise AppException("New role is required")
            
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError(f"User with ID {user_id} not found")
        old_role = user.role
        user.role = new_role
        await self.db.commit()
        await self.db.refresh(user)
        logger.info("user_role_updated", user_id=user_id, old_role=old_role, new_role=new_role)
        
        # FIXED: Create audit log for role update
        audit_service = AuditLogService(self.db)
        await audit_service.create(AuditLogCreate(
            entity_type="users",
            entity_id=user_id,
            action="UPDATE",
            reason=f"Role changed from {old_role} to {new_role}",
            old_values=json.dumps({"role": old_role}),
            new_values=json.dumps({"role": new_role})
        ))
        
        return AdminUserResponse.model_validate(user)


class LenderService:
    """Service for managing lenders and their products."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_lender(self, payload: LenderCreate) -> LenderResponse:
        """Create a new lender.
        
        Args:
            payload: Lender creation data
            
        Returns:
            Created lender response
        """
        # FIXED: Add input validation
        if not payload.name or not payload.code or not payload.contact_email:
            raise AppException("Name, code, and contact email are required")
            
        logger.info("lender_create", name=payload.name)
        instance = Lender(
            name=payload.name,
            code=payload.code,
            contact_email=payload.contact_email,
        )
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        
        # FIXED: Create audit log for lender creation
        audit_service = AuditLogService(self.db)
        await audit_service.create(AuditLogCreate(
            entity_type="lenders",
            entity_id=instance.id,
            action="CREATE",
            reason="New lender created",
            new_values=json.dumps({
                "name": payload.name,
                "code": payload.code,
                "contact_email": payload.contact_email
            })
        ))
        
        return LenderResponse.model_validate(instance)

    async def update_lender(self, lender_id: int, payload: LenderUpdate) -> LenderResponse:
        """Update an existing lender.
        
        Args:
            lender_id: ID of lender to update
            payload: Update data
            
        Returns:
            Updated lender response
            
        Raises:
            NotFoundError: If lender doesn't exist
        """
        # FIXED: Add input validation
        if not isinstance(lender_id, int) or lender_id <= 0:
            raise AppException("Invalid lender ID")
            
        stmt = select(Lender).where(Lender.id == lender_id)
        result = await self.db.execute(stmt)
        lender = result.scalar_one_or_none()
        if not lender:
            raise NotFoundError(f"Lender with ID {lender_id} not found")
            
        # Store old values for audit
        old_values = {
            "name": lender.name,
            "code": lender.code,
            "contact_email": lender.contact_email,
            "is_active": lender.is_active
        }
        
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(lender, key, value)
        await self.db.commit()
        await self.db.refresh(lender)
        logger.info("lender_updated", lender_id=lender_id)
        
        # FIXED: Create audit log for lender update
        audit_service = AuditLogService(self.db)
        await audit_service.create(AuditLogCreate(
            entity_type="lenders",
            entity_id=lender_id,
            action="UPDATE",
            reason="Lender updated",
            old_values=json.dumps(old_values),
            new_values=json.dumps(update_data)
        ))
        
        return LenderResponse.model_validate(lender)

    async def create_product(self, lender_id: int, payload: ProductCreate) -> ProductResponse:
        """Create a new product for a lender.
        
        Args:
            lender_id: ID of lender
            payload: Product creation data
            
        Returns:
            Created product response
            
        Raises:
            NotFoundError: If lender doesn't exist
        """
        # FIXED: Add input validation
        if not isinstance(lender_id, int) or lender_id <= 0:
            raise AppException("Invalid lender ID")
        if payload.rate < 0 or payload.max_ltv < 0 or payload.max_ltv > 100:
            raise AppException("Invalid product parameters")
            
        # Verify lender exists
        stmt = select(Lender).where(Lender.id == lender_id)
        result = await self.db.execute(stmt)
        lender = result.scalar_one_or_none()
        if not lender:
            raise NotFoundError(f"Lender with ID {lender_id} not found")
            
        logger.info("product_create", lender_id=lender_id, product_name=payload.name)
        instance = Product(
            lender_id=lender_id,
            name=payload.name,
            rate=payload.rate,
            max_ltv=payload.max_ltv,
            insurance_required=payload.insurance_required,
        )
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        
        # FIXED: Create audit log for product creation
        audit_service = AuditLogService(self.db)
        await audit_service.create(AuditLogCreate(
            entity_type="products",
            entity_id=instance.id,
            action="CREATE",
            reason="New product created",
            new_values=json.dumps({
                "lender_id": lender_id,
                "name": payload.name,
                "rate": str(payload.rate),
                "max_ltv": str(payload.max_ltv),
                "insurance_required": payload.insurance_required
            })
        ))
        
        return ProductResponse.model_validate(instance)

    async def update_product(self, lender_id: int, product_id: int, payload: ProductUpdate) -> ProductResponse:
        """Update a product.
        
        Args:
            lender_id: ID of lender
            product_id: ID of product
            payload: Update data
            
        Returns:
            Updated product response
            
        Raises:
            NotFoundError: If product doesn't exist
        """
        # FIXED: Add input validation
        if not isinstance(lender_id, int) or lender_id <= 0:
            raise AppException("Invalid lender ID")
        if not isinstance(product_id, int) or product_id <= 0:
            raise AppException("Invalid product ID")
            
        stmt = select(Product).where(Product.id == product_id, Product.lender_id == lender_id)
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundError(f"Product with ID {product_id} not found for lender {lender_id}")
            
        # Store old values for audit
        old_values = {
            "name": product.name,
            "rate": str(product.rate),
            "max_ltv": str(product.max_ltv),
            "insurance_required": product.insurance_required,
            "is_active": product.is_active
        }
        
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(product, key, value)
        await self.db.commit()
        await self.db.refresh(product)
        logger.info("product_updated", product_id=product_id)
        
        # FIXED: Create audit log for product update
        audit_service = AuditLogService(self.db)
        await audit_service.create(AuditLogCreate(
            entity_type="products",
            entity_id=product_id,
            action="UPDATE",
            reason="Product updated",
            old_values=json.dumps(old_values),
            new_values=json.dumps(update_data)
        ))
        
        return ProductResponse.model_validate(product)

    async def deactivate_product(self, lender_id: int, product_id: int) -> ProductResponse:
        """Deactivate a product.
        
        Args:
            lender_id: ID of lender
            product_id: ID of product
            
        Returns:
            Deactivated product response
            
        Raises:
            NotFoundError: If product doesn't exist
        """
        # FIXED: Add input validation
        if not isinstance(lender_id, int) or lender_id <= 0:
            raise AppException("Invalid lender ID")
        if not isinstance(product_id, int) or product_id <= 0:
            raise AppException("Invalid product ID")
            
        stmt = select(Product).where(Product.id == product_id, Product.lender_id == lender_id)
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundError(f"Product with ID {product_id} not found for lender {lender_id}")
            
        product.is_active = False
        await self.db.commit()
        await self.db.refresh(product)
        logger.info("product_deactivated", product_id=product_id)
        
        # FIXED: Create audit log for product deactivation
        audit_service = AuditLogService(self.db)
        await audit_service.create(AuditLogCreate(
            entity_type="products",
            entity_id=product_id,
            action="UPDATE",
            reason="Product deactivated",
            old_values=json.dumps({"is_active": True}),
            new_values=json.dumps({"is_active": False})
        ))
        
        return ProductResponse.model_validate(product)