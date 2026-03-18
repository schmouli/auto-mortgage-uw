from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from sqlalchemy import select, func as sql_func
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.modules.admin_panel.models import AuditLog, Lender, LenderProduct
from mortgage_underwriting.modules.admin_panel.schemas import (
    UserResponse,
    UserListResponse,
    UserRoleUpdate,
    LenderCreate,
    LenderUpdate,
    LenderResponse,
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    AuditLogResponse,
    AuditLogListResponse,
    FintracReportResponse
)
from mortgage_underwriting.modules.auth.models import User  # FIXED: Proper import syntax

logger = structlog.get_logger()


class AdminPanelService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # User Management
    async def list_users(
        self,
        page: int = 1,
        page_size: int = 50,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None
    ) -> UserListResponse:
        logger.info("listing_users", page=page, page_size=page_size)
        
        query = select(User)
        
        if role:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        if search:
            query = query.where(
                (User.email.ilike(f"%{search}%")) |
                (User.full_name.ilike(f"%{search}%"))
            )
            
        # Pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        result = await self.db.execute(query)
        users = result.scalars().all()
        
        # Get total count
        count_query = select(sql_func.count()).select_from(User)
        if role:
            count_query = count_query.where(User.role == role)
        if is_active is not None:
            count_query = count_query.where(User.is_active == is_active)
        if search:
            count_query = count_query.where(
                (User.email.ilike(f"%{search}%")) |
                (User.full_name.ilike(f"%{search}%"))
            )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()
        
        return UserListResponse(
            items=[UserResponse.model_validate(user) for user in users],
            total=total,
            page=page,
            page_size=page_size
        )

    async def deactivate_user(self, user_id: int, reason: str, current_user_id: int) -> UserResponse:  # FIXED: Changed parameter name to reflect actual usage
        logger.info("deactivating_user", user_id=user_id)
        
        user = await self.db.get(User, user_id)
        if not user:
            raise NotFoundError(detail="User not found", error_code="USER_001")
            
        user.is_active = False
        
        # Log audit
        audit_entry = AuditLog(
            user_id=current_user_id,  # FIXED: Using authenticated user ID
            action="DEACTIVATE_USER",
            entity_type="users",
            entity_id=user_id,
            new_value=f"User deactivated: {reason}",
            old_value=None
        )
        self.db.add(audit_entry)
        
        await self.db.commit()
        await self.db.refresh(user)
        
        return UserResponse.model_validate(user)

    async def update_user_role(self, user_id: int, payload: UserRoleUpdate, current_user_id: int) -> UserResponse:  # FIXED: Changed parameter name to reflect actual usage
        logger.info("updating_user_role", user_id=user_id, new_role=payload.role)
        
        user = await self.db.get(User, user_id)
        if not user:
            raise NotFoundError(detail="User not found", error_code="USER_001")
            
        old_role = user.role
        user.role = payload.role
        
        # Log audit
        audit_entry = AuditLog(
            user_id=current_user_id,  # FIXED: Using authenticated user ID
            action="UPDATE_ROLE",
            entity_type="users",
            entity_id=user_id,
            old_value=old_role,
            new_value=payload.role
        )
        self.db.add(audit_entry)
        
        await self.db.commit()
        await self.db.refresh(user)
        
        return UserResponse.model_validate(user)

    # Lender Management
    async def create_lender(self, payload: LenderCreate) -> LenderResponse:
        logger.info("creating_lender", name=payload.name)
        
        lender = Lender(name=payload.name)
        self.db.add(lender)
        await self.db.commit()
        await self.db.refresh(lender)
        
        return LenderResponse.model_validate(lender)

    async def update_lender(self, lender_id: int, payload: LenderUpdate) -> LenderResponse:
        logger.info("updating_lender", lender_id=lender_id)
        
        lender = await self.db.get(Lender, lender_id)
        if not lender:
            raise NotFoundError(detail="Lender not found", error_code="LENDER_001")
            
        lender.name = payload.name
        lender.is_active = payload.is_active
        
        await self.db.commit()
        await self.db.refresh(lender)
        
        return LenderResponse.model_validate(lender)

    async def add_product(self, lender_id: int, payload: ProductCreate) -> ProductResponse:
        logger.info("adding_product", lender_id=lender_id)
        
        lender = await self.db.get(Lender, lender_id)
        if not lender:
            raise NotFoundError(detail="Lender not found", error_code="LENDER_001")
            
        product = LenderProduct(
            lender_id=lender_id,
            name=payload.name,
            min_loan_amount=payload.min_loan_amount,
            max_loan_amount=payload.max_loan_amount,
            interest_rate=payload.interest_rate,
            term_months=payload.term_months
        )
        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product)
        
        return ProductResponse.model_validate(product)

    async def update_product(self, lender_id: int, product_id: int, payload: ProductUpdate) -> ProductResponse:
        logger.info("updating_product", lender_id=lender_id, product_id=product_id)
        
        product = await self.db.get(LenderProduct, product_id)
        if not product or product.lender_id != lender_id:
            raise NotFoundError(detail="Product not found", error_code="PRODUCT_001")
            
        product.name = payload.name
        product.min_loan_amount = payload.min_loan_amount
        product.max_loan_amount = payload.max_loan_amount
        product.interest_rate = payload.interest_rate
        product.term_months = payload.term_months
        product.is_active = payload.is_active
        
        await self.db.commit()
        await self.db.refresh(product)
        
        return ProductResponse.model_validate(product)

    async def deactivate_product(self, lender_id: int, product_id: int) -> ProductResponse:
        logger.info("deactivating_product", lender_id=lender_id, product_id=product_id)
        
        product = await self.db.get(LenderProduct, product_id)
        if not product or product.lender_id != lender_id:
            raise NotFoundError(detail="Product not found", error_code="PRODUCT_001")
            
        product.is_active = False
        
        await self.db.commit()
        await self.db.refresh(product)
        
        return ProductResponse.model_validate(product)

    # Audit Logs
    async def list_audit_logs(
        self,
        page: int = 1,
        page_size: int = 50
    ) -> AuditLogListResponse:
        logger.info("listing_audit_logs", page=page, page_size=page_size)
        
        query = select(AuditLog).order_by(AuditLog.created_at.desc())
        
        # Pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        result = await self.db.execute(query)
        logs = result.scalars().all()
        
        # Get total count
        count_query = select(sql_func.count()).select_from(AuditLog)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()
        
        return AuditLogListResponse(
            items=[AuditLogResponse.model_validate(log) for log in logs],
            total=total,
            page=page,
            page_size=page_size
        )

    # FINTRAC Reports
    async def get_fintrac_reports(self) -> List[FintracReportResponse]:
        logger.info("getting_fintrac_reports")
        # Implementation would go here
        return []