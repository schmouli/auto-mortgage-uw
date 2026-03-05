from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.xml_policy_service.models import XmlPolicyDocument
from mortgage_underwriting.modules.xml_policy_service.schemas import (
    XmlPolicyDocumentCreate,
    XmlPolicyDocumentUpdate,
    XmlPolicyDocumentResponse,
    XmlPolicyDocumentListResponse
)
from mortgage_underwriting.modules.xml_policy_service.services import XmlPolicyDocumentService
from mortgage_underwriting.modules.xml_policy_service.exceptions import XmlPolicyServiceException

router = APIRouter(prefix="/api/v1/xml-policy-documents", tags=["XML Policy Documents"])

@router.post("/", response_model=XmlPolicyDocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_xml_policy_document(
    payload: XmlPolicyDocumentCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Create a new XML policy document.
    
    Raises:
        400: If validation fails
        500: If creation fails
    """
    service = XmlPolicyDocumentService(db)
    try:
        document = await service.create_document(payload)
        return document
    except XmlPolicyServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "POLICY_DOC_CREATE_FAILED"}
        )

@router.get("/{document_id}", response_model=XmlPolicyDocumentResponse)
async def get_xml_policy_document(
    document_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Retrieve an XML policy document by ID.
    
    Raises:
        404: If document not found
    """
    service = XmlPolicyDocumentService(db)
    try:
        document = await service.get_document(document_id)
        return document
    except XmlPolicyServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(e), "error_code": "POLICY_DOC_NOT_FOUND"}
        )

@router.put("/{document_id}", response_model=XmlPolicyDocumentResponse)
async def update_xml_policy_document(
    document_id: int,
    payload: XmlPolicyDocumentUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Update an XML policy document.
    
    Raises:
        404: If document not found
        400: If update fails
    """
    service = XmlPolicyDocumentService(db)
    try:
        document = await service.update_document(document_id, payload)
        return document
    except XmlPolicyServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "POLICY_DOC_UPDATE_FAILED"}
        )

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_xml_policy_document(
    document_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Delete an XML policy document (soft delete).
    
    Raises:
        404: If document not found
        400: If deletion fails
    """
    service = XmlPolicyDocumentService(db)
    try:
        await service.delete_document(document_id)
    except XmlPolicyServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "POLICY_DOC_DELETE_FAILED"}
        )

@router.get("/", response_model=XmlPolicyDocumentListResponse)
async def list_xml_policy_documents(
    application_id: int = Query(..., gt=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),  # FIXED: Enforce max limit of 100
    db: AsyncSession = Depends(get_async_session),
):
    """
    List XML policy documents for an application with pagination.
    
    Query Parameters:
        application_id: Filter by application ID
        skip: Number of records to skip (default: 0)
        limit: Number of records to return (default/max: 100)
        
    Raises:
        400: If query fails
    """
    service = XmlPolicyDocumentService(db)
    try:
        documents, total = await service.get_policy_documents(application_id, skip, limit)
        return XmlPolicyDocumentListResponse(
            items=documents,
            total=total,
            skip=skip,
            limit=limit
        )
    except XmlPolicyServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "POLICY_DOCS_LIST_FAILED"}
        )
```

```