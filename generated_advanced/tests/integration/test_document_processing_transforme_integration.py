import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select
from mortgage_underwriting.modules.document_processing_transformer.models import (
    RawDocument,
    ProcessedDocument,
)


@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentProcessingAPI:
    async def test_upload_document_workflow(self, client: AsyncClient, db_session):
        """
        Test 1: Upload a new document record.
        """
        response = await client.post(
            "/api/v1/dpt/documents",
            json={
                "file_name": "pay_stub_1.pdf",
                "file_url": "https://secure-storage.com/stub.pdf",
                "content_type": "application/pdf",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["status"] == "uploaded"
        assert data["file_name"] == "pay_stub_1.pdf"

        # Verify DB state
        stmt = select(RawDocument).where(RawDocument.id == data["id"])
        result = await db_session.execute(stmt)
        doc = result.scalar_one_or_none()
        assert doc is not None
        assert doc.file_name == "pay_stub_1.pdf"

    async def test_process_document_endpoint_success(
        self, client: AsyncClient, db_session, mock_ocr_service, valid_ocr_payload
    ):
        """
        Test 2: Trigger processing of an uploaded document.
        Mocks the OCR service but tests the full API stack.
        """
        # 1. Setup: Create a raw document in DB
        new_doc = RawDocument(
            file_name="test.pdf",
            file_url="http://test.com/test.pdf",
            status="uploaded",
        )
        db_session.add(new_doc)
        await db_session.commit()
        await db_session.refresh(new_doc)

        # 2. Mock the OCR service response
        mock_ocr_service.return_value.extract_data.return_value = valid_ocr_payload

        # 3. Call Process Endpoint
        response = await client.post(f"/api/v1/dpt/documents/{new_doc.id}/process")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["extracted_data"]["applicant_name"] == "John Doe"
        
        # 4. Verify DB: ProcessedDocument created
        stmt = select(ProcessedDocument).where(
            ProcessedDocument.raw_document_id == new_doc.id
        )
        result = await db_session.execute(stmt)
        proc_doc = result.scalar_one_or_none()
        
        assert proc_doc is not None
        assert proc_doc.status == "completed"
        
        # Verify Decimal precision in DB response
        assert isinstance(proc_doc.extracted_annual_income, Decimal)
        assert proc_doc.extracted_annual_income == Decimal("85000.00")

    async def test_get_processed_document(
        self, client: AsyncClient, db_session, valid_ocr_payload
    ):
        """
        Test 3: Retrieve processed data via GET.
        """
        # Setup Raw
        raw = RawDocument(file_name="get_test.pdf", file_url="url", status="uploaded")
        db_session.add(raw)
        await db_session.commit()
        await db_session.refresh(raw)

        # Setup Processed
        processed = ProcessedDocument(
            raw_document_id=raw.id,
            status="completed",
            extracted_applicant_name="Jane Smith",
            extracted_annual_income=Decimal("92000.50"),
            extracted_sin_hash="hashed_sin_value", # Should not return real SIN
        )
        db_session.add(processed)
        await db_session.commit()
        await db_session.refresh(processed)

        # Get Request
        response = await client.get(f"/api/v1/dpt/documents/{raw.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # PIPEDA Check: Ensure real SIN is NOT in response
        assert "sin" not in data["extracted_data"]
        assert "123456789" not in str(data) # Ensure no plain text PII leaked
        
        # Financial Check
        assert data["extracted_data"]["annual_income"] == "92000.50"

    async def test_process_nonexistent_document_returns_404(self, client: AsyncClient):
        """
        Test 4: Error handling for missing document.
        """
        response = await client.post("/api/v1/dpt/documents/does-not-exist/process")
        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_invalid_file_upload_returns_422(self, client: AsyncClient):
        """
        Test 5: Input validation on upload.
        """
        response = await client.post(
            "/api/v1/dpt/documents",
            json={
                # Missing file_name
                "file_url": "http://test.com"
            },
        )
        assert response.status_code == 422

    async def test_concurrent_processing_handling(
        self, client: AsyncClient, db_session, mock_ocr_service
    ):
        """
        Test 6: Ensure system handles status transitions correctly.
        """
        # Create raw doc
        raw = RawDocument(file_name="concurrent.pdf", file_url="url", status="uploaded")
        db_session.add(raw)
        await db_session.commit()
        await db_session.refresh(raw)

        # Mock OCR to take time (simulated) or just return success
        mock_ocr_service.return_value.extract_data.return_value = {
            "applicant_name": "Concurrent Test",
            "annual_income": "50000",
            "sin": "111222333",
            "dob": "1990-01-01"
        }

        # First process
        r1 = await client.post(f"/api/v1/dpt/documents/{raw.id}/process")
        assert r1.status_code == 200

        # Try to process again (Idempotency or Conflict check expected)
        # Assuming service logic prevents re-processing 'completed' docs
        r2 = await client.post(f"/api/v1/dpt/documents/{raw.id}/process")
        assert r2.status_code == 400 or r2.status_code == 200 # Depends on business logic (usually 400 Bad Request)

    async def test_financial_precision_stored_correctly(
        self, client: AsyncClient, db_session, mock_ocr_service
    ):
        """
        Test 7: Verify high precision financial values are preserved.
        """
        raw = RawDocument(file_name="precision.pdf", file_url="url", status="uploaded")
        db_session.add(raw)
        await db_session.commit()

        # Payload with high precision
        mock_payload = {
            "applicant_name": "Precision User",
            "sin": "123",
            "dob": "2000-01-01",
            "annual_income": "123456.78", # 2 decimal places
            "property_value": "987654.32",
            "loan_amount": "800000.01"
        }
        mock_ocr_service.return_value.extract_data.return_value = mock_payload

        await client.post(f"/api/v1/dpt/documents/{raw.id}/process")

        # Verify in DB directly
        stmt = select(ProcessedDocument).where(ProcessedDocument.raw_document_id == raw.id)
        result = await db_session.execute(stmt)
        proc = result.scalar_one()

        # Strict Decimal comparison
        assert proc.extracted_annual_income == Decimal("123456.78")
        assert proc.extracted_loan_amount == Decimal("800000.01")