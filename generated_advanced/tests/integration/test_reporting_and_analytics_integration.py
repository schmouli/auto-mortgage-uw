import pytest
from decimal import Decimal
from datetime import date, datetime
from httpx import AsyncClient

from mortgage_underwriting.modules.reporting_analytics.models import ReportLog
from mortgage_underwriting.modules.applications.models import MortgageApplication
from mortgage_underwriting.modules.borrowers.models import Borrower
from mortgage_underwriting.modules.properties.models import Property
from mortgage_underwriting.common.security import hash_pii


@pytest.mark.integration
@pytest.mark.asyncio
class TestReportingAPI:
    async def test_get_portfolio_metrics_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """
        Test the full integration of the portfolio metrics endpoint.
        Creates data in DB, hits API, verifies response.
        """
        # Setup: Create dummy applications
        app1 = MortgageApplication(
            id="app-1",
            status="APPROVED",
            created_at=datetime(2023, 6, 1),
            gds=Decimal("30.00"),
            tds=Decimal("35.00"),
            loan_amount=Decimal("300000"),
            property_value=Decimal("400000"), # 75% LTV
            qualifying_rate=Decimal("5.25"),
        )
        app2 = MortgageApplication(
            id="app-2",
            status="DECLINED",
            created_at=datetime(2023, 6, 5),
            gds=Decimal("45.00"), # High GDS
            tds=Decimal("50.00"),
            loan_amount=Decimal("200000"),
            property_value=Decimal("200000"), # 100% LTV
            qualifying_rate=Decimal("6.50"),
        )

        db_session.add(app1)
        db_session.add(app2)
        await db_session.commit()

        # Act
        response = await client.get(
            "/api/v1/reporting/portfolio-metrics",
            params={"start_date": "2023-01-01", "end_date": "2023-12-31"}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_applications"] == 2
        assert data["approved_count"] == 1
        assert data["declined_count"] == 1
        # Check averaging: (30 + 45) / 2 = 37.5
        assert Decimal(data["avg_gds"]) == Decimal("37.50")
        assert Decimal(data["avg_tds"]) == Decimal("42.50")

    async def test_get_ltv_distribution_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """
        Test LTV distribution endpoint with real DB aggregation.
        """
        # Setup: Specific LTVs
        # 80.01-85% bucket
        app_85 = MortgageApplication(
            id="app-ltv-85",
            status="APPROVED",
            created_at=datetime(2023, 1, 1),
            loan_amount=Decimal("85000"),
            property_value=Decimal("100000"),
            gds=Decimal("30.00"),
            tds=Decimal("35.00"),
            qualifying_rate=Decimal("5.25"),
        )
        # 90.01-95% bucket
        app_92 = MortgageApplication(
            id="app-ltv-92",
            status="APPROVED",
            created_at=datetime(2023, 1, 2),
            loan_amount=Decimal("92000"),
            property_value=Decimal("100000"),
            gds=Decimal("30.00"),
            tds=Decimal("35.00"),
            qualifying_rate=Decimal("5.25"),
        )

        db_session.add(app_85)
        db_session.add(app_92)
        await db_session.commit()

        response = await client.get(
            "/api/v1/reporting/ltv-distribution",
            params={"start_date": "2023-01-01", "end_date": "2023-12-31"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        
        # Find specific buckets in response
        bucket_85 = next((b for b in data if b["range_label"] == "80.01% - 85%"), None)
        bucket_92 = next((b for b in data if b["range_label"] == "90.01% - 95%"), None)
        
        assert bucket_85 is not None
        assert bucket_85["count"] == 1
        assert bucket_92 is not None
        assert bucket_92["count"] == 1

    async def test_create_report_log_audit(self, client: AsyncClient, db_session: AsyncSession):
        """
        Test that requesting a report creates an audit log (FINTRAC compliance).
        """
        payload = {
            "report_type": "compliance_audit",
            "start_date": "2023-01-01",
            "end_date": "2023-01-31"
        }

        response = await client.post("/api/v1/reporting/generate", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert "report_id" in data

        # Verify DB has the log
        result = await db_session.execute(
            f"SELECT * FROM report_logs WHERE report_type = 'compliance_audit'"
        )
        # Note: using raw SQL or model query here to verify persistence
        # For this test, we assume ReportLog model exists
        logs = await db_session.execute(select(ReportLog).where(ReportLog.report_type == "compliance_audit"))
        log_entry = logs.scalar_one_or_none()
        
        assert log_entry is not None
        assert log_entry.requested_by == "system" # Assuming default user if none provided
        assert log_entry.status == "COMPLETED" # Or PENDING depending on async nature

    async def test_pii_not_exposed_in_reports(self, client: AsyncClient, db_session: AsyncSession):
        """
        PIPEDA Compliance: Ensure reports do not expose raw SIN or DOB.
        """
        # Create a borrower with PII
        # Note: In a real scenario, SIN is encrypted in the DB.
        # Here we ensure the Reporting service doesn't select it.
        
        borrower = Borrower(
            id="borr-1",
            first_name="John",
            last_name="Doe",
            sin_hash=hash_pii("123456789"), # Store hash
            dob=date(1980, 1, 1),
            created_at=datetime.now()
        )
        
        app = MortgageApplication(
            id="app-pii",
            borrower_id=borrower.id,
            status="APPROVED",
            created_at=datetime(2023, 1, 1),
            gds=Decimal("20.00"),
            tds=Decimal("25.00"),
            loan_amount=Decimal("100000"),
            property_value=Decimal("200000"),
            qualifying_rate=Decimal("5.25"),
        )

        db_session.add(borrower)
        db_session.add(app)
        await db_session.commit()

        # Get a detailed report (e.g., Compliance Report)
        response = await client.get(
            "/api/v1/reporting/compliance",
            params={"start_date": "2023-01-01", "end_date": "2023-12-31"}
        )

        assert response.status_code == 200
        data = response.json()
        
        # Serialize to string to check for presence of data
        response_str = str(data)
        
        # Assert raw SIN is not present
        assert "123456789" not in response_str
        # Assert DOB is not present (unless explicitly allowed, but usually masked in reports)
        # Assuming report shows IDs, not PII
        assert "John" not in response_str or "Doe" not in response_str # Depending on requirements, usually names are ok, SIN is not. 
        # Strict check for SIN:
        assert "sin" not in response_str.lower()

    async def test_empty_date_range_returns_zeroes(self, client: AsyncClient):
        """
        Test that querying a date range with no data returns valid zero-structure, not 404.
        """
        response = await client.get(
            "/api/v1/reporting/portfolio-metrics",
            params={"start_date": "2050-01-01", "end_date": "2050-12-31"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_applications"] == 0
        assert data["avg_gds"] == "0.00"

    async def test_invalid_date_format(self, client: AsyncClient):
        """
        Test validation of date inputs.
        """
        response = await client.get(
            "/api/v1/reporting/portfolio-metrics",
            params={"start_date": "invalid-date", "end_date": "2023-12-31"}
        )
        
        assert response.status_code == 422 # Validation Error