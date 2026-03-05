import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from mortgage_underwriting.modules.admin_panel.models import AdminUser, SupportAgent, Role
from mortgage_underwriting.modules.admin_panel.schemas import AdminUserCreate, AdminUserUpdate, SupportAgentCreate, RoleCreate
from mortgage_underwriting.modules.admin_panel.exceptions import AdminPanelException

logger = structlog.get_logger()


class AdminPanelService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_admin_user(self, payload: AdminUserCreate) -> AdminUser:
        """Create a new admin user."""
        logger.info("creating_admin_user", email=payload.email)
        instance = AdminUser(**payload.model_dump())
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def get_admin_user(self, user_id: int) -> AdminUser:
        """Get an admin user by ID."""
        stmt = select(AdminUser).where(AdminUser.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise AdminPanelException("Admin user not found")
        return user

    async def list_admin_users(self, *, skip: int = 0, limit: int = 100) -> List[AdminUser]:
        """List admin users with pagination."""
        stmt = select(AdminUser).offset(skip).limit(min(limit, 100))
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def update_admin_user(self, user_id: int, payload: AdminUserUpdate) -> AdminUser:
        """Update an existing admin user."""
        user = await self.get_admin_user(user_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete_admin_user(self, user_id: int) -> None:
        """Delete an admin user."""
        user = await self.get_admin_user(user_id)
        await self.db.delete(user)
        await self.db.commit()

    async def create_support_agent(self, payload: SupportAgentCreate) -> SupportAgent:
        """Create a new support agent."""
        logger.info("creating_support_agent", name=payload.name)
        instance = SupportAgent(**payload.model_dump())
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def create_role(self, payload: RoleCreate) -> Role:
        """Create a new role."""
        logger.info("creating_role", name=payload.name)
        instance = Role(**payload.model_dump())
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance
```

```