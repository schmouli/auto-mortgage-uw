from sqlalchemy import Integer, String, DateTime, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from typing import Dict, Any

from mortgage_underwriting.common.database import Base


class FrontendComponent(Base):
    __tablename__ = "frontend_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    component_type: Mapped[str] = mapped_column(String(50), nullable=False)
    props: Mapped[Dict[str, Any]] = mapped_column(Text, nullable=True)  # FIXED: Added proper type hint
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())  # FIXED: Ensured timezone=True
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # FIXED: Ensured timezone=True