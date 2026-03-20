from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, String, DateTime, ForeignKey, Boolean, Text, Numeric, CheckConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from typing import Optional, List

from mortgage_underwriting.common.database import Base


class FrontendUIModule(Base):
    __tablename__ = "frontend_ui_modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    ui_components: Mapped[List["UIComponent"]] = relationship("UIComponent", back_populates="module")


class UIComponent(Base):
    __tablename__ = "ui_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    module_id: Mapped[int] = mapped_column(Integer, ForeignKey("frontend_ui_modules.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    component_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., uploader, chart, etc.
    configuration: Mapped[Optional[str]] = mapped_column(Text)  # JSON config blob
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Constraints
    __table_args__ = (
        CheckConstraint("LENGTH(name) > 0", name="name_not_empty"),
        CheckConstraint("LENGTH(component_type) > 0", name="component_type_not_empty"),
    )

    # Relationships
    module: Mapped["FrontendUIModule"] = relationship("FrontendUIModule", back_populates="ui_components")