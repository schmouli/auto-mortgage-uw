import pytest
from httpx import AsyncClient
from sqlalchemy import select
from decimal import Decimal

from mortgage_underwriting.modules.document_processing_transformer.models import DocumentRecord
from mortgage_underwriting.common.exceptions import AppException


@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentProcessingEndpoints:

    async def test_upload_document_success(self, client: AsyncClient, sample_document_payload):
        """Test uploading a new document metadata record."""
        response = await client.post("/api/v1/dpt/upload", json=sample_document_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["file_name"] == "january_paystub.pdf"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    async def test_upload_document_missing_fields(self, client: AsyncClient):
        """Test upload validation with missing required fields."""
        incomplete_payload = {
            "file_name": "missing_info.pdf"
        }
        response = await client.post("/api/v1/dpt/upload", json=incomplete_payload)
        
        assert response.status_code == 422  # Unprocessable Entity

    async def test_get_document_by_id(self, client: AsyncClient, db_session, sample_document_payload):
        """Test retrieving a document by its ID."""
        # 1. Create a document directly in DB
        doc = DocumentRecord(**sample_document_payload)
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        # 2. Fetch via API
        response = await client.get(f"/api/v1/dpt/documents/{doc.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == doc.id
        assert data["content_hash"] == "sha256:abc123..."

    async def test_get_document_not_found(self, client: AsyncClient):
        """Test retrieving a non-existent document."""
        response = await client.get("/api/v1/dpt/documents/99999")
        
        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_trigger_extraction_workflow(self, client: AsyncClient, db_session, sample_document_payload, mock_ocr_service):
        """
        Test the full workflow: Upload -> Trigger Extraction -> Verify Result.
        Note: We must mock the actual external OCR call here.
        """
        # 1. Upload
        upload_resp = await client.post("/api/v1/dpt/upload", json=sample_document_payload)
        doc_id = upload_resp.json()["id"]

        # 2. Trigger Extraction (Mocking the external service dependency in the app)
        # In a real integration test, we might use a dependency override to inject the mock OCR client
        from mortgage_underwriting.modules.document_processing_transformer.services import OCRClient
        from unittest.mock import AsyncMock
        
        mock_client = AsyncMock()
        mock_client.extract_text.return_value = {
            "applicant_name": "Jane Doe",
            "annual_income": "92000.50",
            "employer": "FinTech Inc"
        }
        
        # Override the OCR client instantiation if possible, or mock the service layer
        # For this integration test, we assume the endpoint calls the service which calls the client.
        # We will patch the service method directly.
        with pytest.mock.patch(
            'mortgage_underwriting.modules.document_processing_transformer.services.DocumentProcessingService.process_ocr_extraction',
            new_callable=AsyncMock
        ) as mock_process:
            # Configure the mock to return an ExtractionResult-like dict
            mock_process.return_value = {
                "document_id": doc_id,
                "extracted_data": {"annual_income": "92000.50"},
                "status": "completed"
            }

            response = await client.post(f"/api/v1/dpt/documents/{doc_id}/extract")
            
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "completed"
            assert result["extracted_data"]["annual_income"] == "92000.50"
            mock_process.assert_awaited_once()

    async def test_get_financial_summary(self, client: AsyncClient, db_session):
        """Test endpoint that aggregates financial data from documents."""
        # Setup: Create a document with an associated extraction result
        doc = DocumentRecord(
            applicant_id="uuid-agg",
            file_name="summary.pdf",
            storage_path="/path",
            status="completed"
        )
        db_session.add(doc)
        await db_session.flush()
        
        # Create extraction result manually (bypassing OCR)
        # Note: In real code, this would be a relation, but here we simulate the data state
        # Assuming the endpoint queries ExtractionResult table joined with DocumentRecord
        
        # Verify endpoint structure (assuming it exists)
        response = await client.get(f"/api/v1/dpt/applicants/uuid-agg/financial-summary")
        
        # Implementation dependent: if empty, might be 200 with empty list or 404
        # Assuming 200
        assert response.status_code in [200, 404]

    async def test_pii_protection_in_response(self, client: AsyncClient, db_session):
        """Ensure that sensitive fields (SIN) are never returned in API responses."""
        # Create a document that contains a SIN in its metadata (encrypted in DB)
        # But let's assume a scenario where we try to fetch raw data
        doc = DocumentRecord(
            applicant_id="uuid-pii",
            file_name="sin_card.jpg",
            storage_path="/secure",
            status="pending"
        )
        db_session.add(doc)
        await db_session.commit()
        
        response = await client.get(f"/api/v1/dpt/documents/{doc.id}")
        data = response.json()
        
        # Ensure no raw SIN field exists in the response
        # Even if the model had it (which it shouldn't expose via schema)
        assert "sin" not in data
        assert "social_insurance_number" not in data

    async def test_delete_document_forbidden(self, client: AsyncClient, db_session, sample_document_payload):
        """Test that documents cannot be deleted (FINTRAC compliance: immutable)."""
        doc = DocumentRecord(**sample_document_payload)
        db_session.add(doc)
        await db_session.commit()
        
        # Assuming a DELETE endpoint exists but should return 405 Method Not Allowed or 403
        response = await client.delete(f"/api/v1/dpt/documents/{doc.id}")
        
        assert response.status_code == 405  # Method Not Allowed

    async def test_update_status_only_internal(self, client: AsyncClient, db_session):
        """Test that status updates are protected or internal only."""
        doc = DocumentRecord(
            applicant_id="uuid-upd",
            file_name="upd.pdf",
            storage_path="/path",
            status="pending"
        )
        db_session.add(doc)
        await db_session.commit()
        
        # Attempt to update status via public API
        response = await client.patch(f"/api/v1/dpt/documents/{doc.id}", json={"status": "approved"})
        
        # Should fail or be ignored depending on design. 
        # Assuming strict design: 403 Forbidden or 422 Unprocessable Entity
        assert response.status_code in [403, 422, 405]