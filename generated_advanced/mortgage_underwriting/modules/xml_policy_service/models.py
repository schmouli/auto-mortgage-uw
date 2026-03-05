from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Boolean, Text, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from decimal import Decimal
from mortgage_underwriting.common.database import Base

class XmlPolicyDocument(Base):
    """
    Model representing an XML policy document associated with a mortgage application.
    
    Regulatory Compliance:
    - FINTRAC: Immutable audit trail with created_at timestamp
    - PIPEDA: Fields are non-sensitive; actual PII stored elsewhere
    """
    __tablename__ = "xml_policy_documents"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("mortgage_applications.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_size_kb: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)  # FIXED: Changed from Float to Decimal
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )  # FIXED: Added updated_at with onupdate

    # Relationships
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", back_populates="policy_documents")

# FIXED: Added composite index for common query pattern
Index('ix_xml_policy_documents_application_created', XmlPolicyDocument.application_id, XmlPolicyDocument.created_at)
```

```