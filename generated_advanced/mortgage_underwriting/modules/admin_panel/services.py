from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import json

from sqlalchemy import select, and_, desc, func as sql_func
from sqlalchemy.exc import IntegrityError
import structlog

from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.modules.admin.models import AuditLog
from mortgage_underwriting.modules.admin.schemas import (
    AdminUserListQuery, AdminUserResponse, UserDeactivateRequest,
    UserRoleUpdateRequest, UserStatusResponse, LenderCreate, LenderUpdate,
    LenderProductCreate, LenderProductUpdate, AuditLogResponse, FintracReportResponse
)
from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.modules.lender.models import Lender, LenderProduct

logger = structlog.get_logger()


class AdminService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_users(self, query: AdminUserListQuery) -> List[AdminUserResponse]:
        logger.info("listing_users", page=query.page, limit=query.limit)
        
        stmt = select(User)
        if query.search:
            stmt = stmt.where(
                (User.email.ilike(f"%{query.search}%")) |
                (User.full_name.ilike(f"%{query.search}%"))
            )
        if query.role:
            stmt = stmt.where(User.role == query.role.value)
            
        stmt = stmt.offset((query.page - 1) * query.limit).limit(query.limit)
        result = await self.db.execute(stmt)
        users = result.scalars().all()
        
        return [AdminUserResponse.model_validate(user) for user in users]

    async def deactivate_user(self, user_id: int, payload: UserDeactivateRequest, admin_id: int) -> UserStatusResponse:
        logger.info("deactivating_user", user_id=user_id, admin_id=admin_id)
        
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise NotFoundError(detail="User not found", error_code="ADMIN_001")
            
        if not user.is_active:
            raise AppException(detail="User already deactivated", error_code="ADMIN_005")
            
        user.is_active = False
        await self.db.commit()
        
        # Log audit entry
        audit_entry = AuditLog(
            user_id=admin_id,
            action="USER_DEACTIVATE",
            entity_type="users",
            entity_id=user_id,
            new_value=json.dumps({"reason": payload.reason}),
        )
        self.db.add(audit_entry)
        await self.db.commit()
        
        return UserStatusResponse(
            user_id=user_id,
            is_active=False,
            deactivated_at=datetime.utcnow(),
            deactivated_by=admin_id
        )

    async def update_user_role(self, user_id: int, payload: UserRoleUpdateRequest, admin_id: int) -> AdminUserResponse:
        logger.info("updating_user_role", user_id=user_id, new_role=payload.new_role, admin_id=admin_id)
        
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise NotFoundError(detail="User not found", error_code="ADMIN_001")
            
        old_role = user.role
        user.role = payload.new_role.value
        await self.db.commit()
        
        # Log audit entry
        audit_entry = AuditLog(
            user_id=admin_id,
            action="USER_ROLE_CHANGE",
            entity_type="users",
            entity_id=user_id,
            old_value=json.dumps({"role": old_role}),
            new_value=json.dumps({"role": payload.new_role.value, "justification": payload.justification}),
        )
        self.db.add(audit_entry)
        await self.db.commit()
        
        return AdminUserResponse.model_validate(user)

    async def create_lender(self, payload: LenderCreate) -> Lender:
        logger.info("creating_lender", name=payload.name)
        
        try:
            lender = Lender(**payload.model_dump())
            self.db.add(lender)
            await self.db.commit()
            await self.db.refresh(lender)
            
            return lender
        except IntegrityError as e:
            await self.db.rollback()
            logger.error("lender_creation_failed", error=str(e))
            raise AppException(detail="Failed to create lender", error_code="ADMIN_006")

    async def update_lender(self, lender_id: int, payload: LenderUpdate) -> Lender:
        logger.info("updating_lender", lender_id=lender_id)
        
        stmt = select(Lender).where(Lender.id == lender_id)
        result = await self.db.execute(stmt)
        lender = result.scalar_one_or_none()
        
        if not lender:
            raise NotFoundError(detail="Lender not found", error_code="ADMIN_002")
            
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(lender, field, value)
            
        await self.db.commit()
        await self.db.refresh(lender)
        
        return lender

    async def add_product_to_lender(self, lender_id: int, payload: LenderProductCreate) -> LenderProduct:
        logger.info("adding_product_to_lender", lender_id=lender_id)
        
        stmt = select(Lender).where(Lender.id == lender_id)
        result = await self.db.execute(stmt)
        lender = result.scalar_one_or_none()
        
        if not lender:
            raise NotFoundError(detail="Lender not found", error_code="ADMIN_002")
            
        try:
            product = LenderProduct(lender_id=lender_id, **payload.model_dump())
            self.db.add(product)
            await self.db.commit()
            await self.db.refresh(product)
            
            return product
        except IntegrityError as e:
            await self.db.rollback()
            logger.error("product_creation_failed", error=str(e))
            raise AppException(detail="Failed to create product", error_code="ADMIN_007")

    async def update_lender_product(self, lender_id: int, product_id: int, payload: LenderProductUpdate) -> LenderProduct:
        logger.info("updating_lender_product", lender_id=lender_id, product_id=product_id)
        
        stmt = select(LenderProduct).where(
            and_(LenderProduct.id == product_id, LenderProduct.lender_id == lender_id)
        )
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()
        
        if not product:
            raise NotFoundError(detail="Product not found for this lender", error_code="ADMIN_003")
            
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(product, field, value)
            
        await self.db.commit()
        await self.db.refresh(product)
        
        return product

    async def deactivate_lender_product(self, lender_id: int, product_id: int) -> LenderProduct:
        logger.info("deactivating_lender_product", lender_id=lender_id, product_id=product_id)
        
        stmt = select(LenderProduct).where(
            and_(LenderProduct.id == product_id, LenderProduct.lender_id == lender_id)
        )
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()
        
        if not product:
            raise NotFoundError(detail="Product not found for this lender", error_code="ADMIN_003")
            
        product.is_active = False
        await self.db.commit()
        await self.db.refresh(product)
        
        return product

    async def list_audit_logs(self, page: int = 1, limit: int = 20) -> List[AuditLogResponse]:
        logger.info("listing_audit_logs", page=page, limit=limit)
        
        stmt = select(AuditLog).order_by(desc(AuditLog.created_at)).offset((page - 1) * limit).limit(limit)
        result = await self.db.execute(stmt)
        logs = result.scalars().all()
        
        return [AuditLogResponse.model_validate(log) for log in logs]

    async def get_fintrac_reports(self) -> List[FintracReportResponse]:
        logger.info("getting_fintrac_reports")
        
        # This would typically fetch from a FINTRAC reports table
        # For now returning mock data
        return [
            FintracReportResponse(
                report_id="FR20231201001",
                generated_at=datetime(2023, 12, 1, 10, 30, 0),
                total_records=42,
                high_risk_count=3,
                total_value_cad=Decimal("2850000.00")
            )
        ]