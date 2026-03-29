from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Tuple

from .models import AuditLog
from .schemas import (
    UserListResponse,
    UserDeactivateRequest,
    UserDeactivateResponse,
    UserRoleChangeRequest,
    UserRoleChangeResponse,
    LenderCreate,
    LenderUpdate,
    LenderProductCreate,
    LenderProductUpdate
)
from sqlalchemy import select, update, func as sql_func
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.modules.lender.models import Lender, LenderProduct

logger = structlog.get_logger()

class AdminService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # --- USER MANAGEMENT ---

    async def list_users(
        self,
        page: int = 1,
        limit: int = 50,
        status: Optional[str] = None,
        role: Optional[str] = None,
        search: Optional[str] = None
    ) -> UserListResponse:
        logger.info("listing_users", page=page, limit=limit, status=status, role=role, search=search)
        
        # Validate inputs
        if not isinstance(page, int) or page < 1:
            raise ValueError("Page must be >= 1")
        if not isinstance(limit, int) or limit < 1 or limit > 200:
            raise ValueError("Limit must be between 1 and 200")
            
        offset = (page - 1) * limit
        stmt = select(User)
        
        if status:
            if status not in ("active", "inactive", "pending"):
                raise ValueError("Invalid status filter")
            stmt = stmt.where(User.is_active == (status == "active"))
        if role:
            if role not in ("admin", "underwriter", "read_only"):
                raise ValueError("Invalid role filter")
            stmt = stmt.where(User.role == role)
        if search:
            stmt = stmt.where(
                User.email.ilike(f"%{search}%") |
                User.full_name.ilike(f"%{search}%")
            )
        
        count_stmt = select(sql_func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()
        
        stmt = stmt.offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        users = result.scalars().all()
        
        items = [
            {
                "id": u.id,
                "email": u.email,
                "first_name": u.full_name.split()[0] if u.full_name else "",
                "last_name": " ".join(u.full_name.split()[1:]) if u.full_name and len(u.full_name.split()) > 1 else "",
                "role": u.role,
                "status": "active" if u.is_active else "inactive",
                "last_login_at": None, # Not tracked in current model
                "created_at": u.created_at
            }
            for u in users
        ]
        
        return UserListResponse(items=items, total=total, page=page, limit=limit)

    async def deactivate_user(self, user_id: int, payload: UserDeactivateRequest, admin_id: int) -> UserDeactivateResponse:
        logger.info("deactivating_user", user_id=user_id, admin_id=admin_id)
        
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("Invalid user ID")
        if not isinstance(admin_id, int) or admin_id <= 0:
            raise ValueError("Invalid admin ID")
        
        if user_id == admin_id:
            raise AppException("Cannot deactivate yourself")
        
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise AppException("User not found")
        
        user.is_active = False
        await self.db.commit()
        await self.db.refresh(user)
        
        # Log audit
        audit_entry = AuditLog(
            user_id=admin_id,
            action="USER_DEACTIVATE",
            entity_type="users",
            entity_id=user_id,
            new_value=f"Status changed to inactive. Reason: {payload.reason}",
        )
        self.db.add(audit_entry)
        await self.db.commit()
        
        return UserDeactivateResponse(
            id=user.id,
            status="inactive",
            deactivated_at=user.updated_at,
            deactivated_by=admin_id
        )

    async def change_user_role(self, user_id: int, payload: UserRoleChangeRequest, admin_id: int) -> UserRoleChangeResponse:
        logger.info("changing_user_role", user_id=user_id, new_role=payload.new_role, admin_id=admin_id)
        
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("Invalid user ID")
        if not isinstance(admin_id, int) or admin_id <= 0:
            raise ValueError("Invalid admin ID")
        
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise AppException("User not found")
        
        old_role = user.role
        user.role = payload.new_role
        await self.db.commit()
        await self.db.refresh(user)
        
        # Log audit
        audit_entry = AuditLog(
            user_id=admin_id,
            action="USER_ROLE_CHANGE",
            entity_type="users",
            entity_id=user_id,
            old_value=old_role,
            new_value=payload.new_role,
        )
        self.db.add(audit_entry)
        await self.db.commit()
        
        return UserRoleChangeResponse(
            id=user.id,
            role=user.role,
            updated_at=user.updated_at
        )

    # --- LENDER MANAGEMENT ---

    async def create_lender(self, payload: LenderCreate) -> Lender:
        logger.info("creating_lender", name=payload.name)
        lender = Lender(**payload.model_dump())
        self.db.add(lender)
        await self.db.commit()
        await self.db.refresh(lender)
        return lender

    async def update_lender(self, lender_id: int, payload: LenderUpdate) -> Lender:
        logger.info("updating_lender", lender_id=lender_id)
        
        if not isinstance(lender_id, int) or lender_id <= 0:
            raise ValueError("Invalid lender ID")
        
        stmt = select(Lender).where(Lender.id == lender_id)
        result = await self.db.execute(stmt)
        lender = result.scalar_one_or_none()
        
        if not lender:
            raise AppException("Lender not found")
        
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(lender, key, value)
        
        await self.db.commit()
        await self.db.refresh(lender)
        return lender

    async def add_product(self, payload: LenderProductCreate) -> LenderProduct:
        logger.info("adding_product", lender_id=payload.lender_id, product_name=payload.product_name)
        
        # Validate lender exists
        stmt = select(Lender).where(Lender.id == payload.lender_id)
        result = await self.db.execute(stmt)
        lender = result.scalar_one_or_none()
        
        if not lender:
            raise AppException("Lender not found")
        
        product = LenderProduct(**payload.model_dump())
        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product)
        return product

    async def update_product(self, prod_id: int, payload: LenderProductUpdate) -> LenderProduct:
        logger.info("updating_product", product_id=prod_id)
        
        if not isinstance(prod_id, int) or prod_id <= 0:
            raise ValueError("Invalid product ID")
        
        stmt = select(LenderProduct).where(LenderProduct.id == prod_id)
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()
        
        if not product:
            raise AppException("Product not found")
        
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(product, key, value)
        
        await self.db.commit()
        await self.db.refresh(product)
        return product

    async def deactivate_product(self, prod_id: int) -> dict:
        logger.info("deactivating_product", product_id=prod_id)
        
        if not isinstance(prod_id, int) or prod_id <= 0:
            raise ValueError("Invalid product ID")
        
        stmt = select(LenderProduct).where(LenderProduct.id == prod_id)
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()
        
        if not product:
            raise AppException("Product not found")
        
        product.is_active = False
        await self.db.commit()
        await self.db.refresh(product)
        
        return {"message": "Product deactivated successfully", "product_id": prod_id}

    async def get_audit_logs(
        self,
        page: int = 1,
        limit: int = 50,
        entity_type: Optional[str] = None,
        action: Optional[str] = None
    ) -> Tuple[List[AuditLog], int]:
        logger.info("fetching_audit_logs", page=page, limit=limit, entity_type=entity_type, action=action)
        
        offset = (page - 1) * limit
        stmt = select(AuditLog)
        
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        
        stmt = stmt.order_by(AuditLog.created_at.desc())
        
        count_stmt = select(sql_func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()
        
        stmt = stmt.offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        logs = result.scalars().all()
        
        return logs, total

    async def get_fintrac_reports(self) -> dict:
        # Placeholder implementation - actual FINTRAC reporting would involve complex logic
        logger.info("generating_fintrac_reports")
        return {
            "report_type": "FINTRAC Summary",
            "generated_at": "2023-04-01T00:00:00Z",
            "data": {
                "large_transactions": 0,
                "suspicious_activities": 0,
                "compliance_status": "OK"
            }
        }