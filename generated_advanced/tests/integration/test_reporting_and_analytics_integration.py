import pytest
from decimal import Decimal
from sqlalchemy import select
from mortgage_underwriting.modules.reporting.models import Report, Application
from mortgage_underwriting.modules.reporting.schemas import ReportType

@pytest.mark.integration
@pytest.mark.asyncio
class TestReportingEndpoints:

    async def test_create_report_request(self, client, db_session):
        """
        Test creating a new report request via API.
        """
        payload = {
            "report_type": "portfolio_summary",
            "start_date": "2023-01-01",
            "end_date": "2023-01-31"
        }

        response = await client.post("/api/v1/reporting/reports", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["report_type"] == "portfolio_summary"
        assert data["status"] == "completed" # Assuming synchronous generation for simplicity or async acceptance
        
        # Verify DB record
        stmt = select(Report).where(Report.id == data["id"])
        result = await db_session.execute(stmt)
        report = result.scalar_one()
        assert report is not None

    async def test_get_report_by_id(self, client, db_session):
        """
        Test retrieving a specific report.
        """
        # Seed a report
        new_report = Report(
            report_type=ReportType.COMPLIANCE_AUDIT,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            status="completed",
            generated_by="system"
        )
        db_session.add(new_report)
        await db_session.commit()
        await db_session.refresh(new_report)

        response = await client.get(f"/api/v1/reporting/reports/{new_report.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == new_report.id
        assert data["report_type"] == "compliance_audit"

    async def test_get_report_not_found(self, client):
        """
        Test 404 when requesting a non-existent report.
        """
        response = await client.get("/api/v1/reporting/reports/99999")
        assert response.status_code == 404

    async def test_list_reports(self, client, db_session):
        """
        Test listing all reports with pagination.
        """
        # Seed multiple reports
        for i in range(3):
            db_session.add(Report(
                report_type=ReportType.PORTFOLIO_SUMMARY,
                start_date=date(2023, 1, 1),
                end_date=date(2023, 1, 31),
                status="completed",
                generated_by="test_user"
            ))
        await db_session.commit()

        response = await client.get("/api/v1/reporting/reports?limit=2&offset=0")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 3

    async def test_invalid_date_range(self, client):
        """
        Test validation error when end_date is before start_date.
        """
        payload = {
            "report_type": "portfolio_summary",
            "start_date": "2023-12-31",
            "end_date": "2023-01-01"
        }

        response = await client.post("/api/v1/reporting/reports", json=payload)
        
        assert response.status_code == 422 # Validation Error

    async def test_portfolio_analytics_endpoint(self, client, db_session):
        """
        Test the analytics aggregation endpoint with real data.
        """
        # Seed Applications
        # App 1: LTV 80%
        app1 = Application(
            id=1,
            applicant_id=1,
            loan_amount=Decimal("80000.00"),
            property_value=Decimal("100000.00"),
            status="approved",
            created_at=datetime(2023, 6, 15)
        )
        # App 2: LTV 50%
        app2 = Application(
            id=2,
            applicant_id=2,
            loan_amount=Decimal("50000.00"),
            property_value=Decimal("100000.00"),
            status="approved",
            created_at=datetime(2023, 6, 20)
        )
        
        db_session.add(app1)
        db_session.add(app2)
        await db_session.commit()

        response = await client.get("/api/v1/reporting/analytics/portfolio?start_date=2023-01-01&end_date=2023-12-31")

        assert response.status_code == 200
        data = response.json()
        
        assert data["total_applications"] == 2
        assert data["total_volume"] == Decimal("130000.00")
        # Average LTV = (80 + 50) / 2 = 65%
        assert data["average_ltv"] == Decimal("65.00")

    async def test_analytics_filters_by_status(self, client, db_session):
        """
        Test that analytics correctly filters by application status.
        """
        # Approved App
        app_approved = Application(
            id=1,
            applicant_id=1,
            loan_amount=Decimal("100000.00"),
            property_value=Decimal("100000.00"),
            status="approved",
            created_at=datetime(2023, 1, 1)
        )
        # Declined App (should be excluded)
        app_declined = Application(
            id=2,
            applicant_id=2,
            loan_amount=Decimal("100000.00"),
            property_value=Decimal("100000.00"),
            status="declined",
            created_at=datetime(2023, 1, 2)
        )

        db_session.add(app_approved)
        db_session.add(app_declined)
        await db_session.commit()

        response = await client.get("/api/v1/reporting/analytics/portfolio?status=approved")

        assert response.status_code == 200
        data = response.json()
        assert data["total_applications"] == 1
        assert data["total_volume"] == Decimal("100000.00")

    async def test_security_headers_present(self, client):
        """
        Test that security headers are present on API responses.
        """
        response = await client.get("/api/v1/reporting/reports")
        assert "X-Content-Type-Options" in response.headers