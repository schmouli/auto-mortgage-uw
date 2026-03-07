from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, DateTime, ForeignKey, Text, Integer, Boolean, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from mortgage_underwriting.common.database import Base

class UiComponent(Base):
    __tablename__ = "ui_components"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    component_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., uploader, progress_indicator
    config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON configuration
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class UiPage(Base):
    __tablename__ = "ui_pages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    route_path: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)  # e.g., /application-status
    page_title: Mapped[str] = mapped_column(String(200), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    components: Mapped[List["PageComponent"]] = relationship("PageComponent", back_populates="page", cascade="all, delete-orphan")

class PageComponent(Base):
    __tablename__ = "page_components"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("ui_pages.id", ondelete="CASCADE"), nullable=False)
    component_id: Mapped[int] = mapped_column(ForeignKey("ui_components.id", ondelete="CASCADE"), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    config_override_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Override default component config
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    page: Mapped["UiPage"] = relationship("UiPage", back_populates="components")
    component: Mapped["UiComponent"] = relationship("UiComponent")