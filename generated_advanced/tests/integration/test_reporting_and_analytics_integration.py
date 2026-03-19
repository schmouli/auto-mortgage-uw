import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select

# Import models from conftest (they represent the DB state)
from conftest import MortgageApplication, AuditLog

@pytest.mark.integration
@pytest.mark.asyncio
class TestReportingEndpoints:

    async def test_get_portfolio_summary_empty(self, client: AsyncClient, db_session):
        # Ensure DB is empty
        result = await client.get("/api/v1/reporting/portfolio-summary")
        assert result.status_code == 200
        
        data = result.json()
        assert data["total_applications"] == 0
        assert data["total_loan_volume"] == "0.00"
        assert data["average_income"] is None or data["average_income"] == "0.00"

    async def test_get_portfolio_summary_with_data(self, client: AsyncClient, db_session, sample_application_data):
        # Create 2 applications
        app1 = MortgageApplication(**sample_application_data)
        app2 = MortgageApplication(**{**sample_application_data, "applicant_id": "cust_456", "principal_amount": Decimal("500000.00")})
        
        db_session.add(app1)
        db_session.add(app2)
        await db_session.commit()

        result = await client.get("/api/v1/reporting/portfolio-summary")
        assert result.status_code == 200
        
        data = result.json()
        assert data["total_applications"] == 2
        # 450k + 500k = 950k
        assert Decimal(data["total_loan_volume"]) == Decimal("950000.00")

    async def test_get_gds_tds_report(self, client: AsyncClient, db_session, sample_application_data):
        # Create a specific scenario
        # Loan: 450k, Rate: 4.5% (Qualifying: 6.5%). 25yr amort (approx).
        # Monthly Mortgage Payment ~ $3000 (simplified for logic check)
        app = MortgageApplication(**sample_application_data)
        db_session.add(app)
        await db_session.commit()

        result = await client.get("/api/v1/reporting/gds-tds-stats")
        assert result.status_code == 200

        data = result.json()
        assert "avg_gds" in data
        assert "avg_tds" in data
        # Check that values are returned as strings to preserve precision
        assert isinstance(data["avg_gds"], str)
        # Verify OSFI B-20 compliance check flag exists
        assert "stress_test_violations" in data

    async def test_get_compliance_report_fintrac(self, client: AsyncClient, db_session, sample_audit_log_data):
        # Add valid log
        log1 = AuditLog(**sample_audit_log_data)
        # Add invalid log (missing performed_by)
        log2 = AuditLog(entity_type="Application", entity_id="app_998", action="CREATE", performed_by=None)
        
        db_session.add(log1)
        db_session.add(log2)
        await db_session.commit()

        result = await client.get("/api/v1/reporting/compliance?days=1")
        assert result.status_code == 200

        data = result.json()
        assert data["total_records"] == 2
        assert data["violations"] == 1
        assert data["compliance_rate"] == "50.00"

    async def test_export_csv_endpoint(self, client: AsyncClient, db_session, sample_application_data):
        app = MortgageApplication(**sample_application_data)
        db_session.add(app)
        await db_session.commit()

        result = await client.post("/api/v1/reporting/export", json={"format": "csv"})
        assert result.status_code == 200
        assert result.headers["content-type"] == "text/csv; charset=utf-8"
        
        content = result.text
        assert "applicant_id" in content
        assert "cust_123" in content

    async def test_export_csv_invalid_format(self, client: AsyncClient):
        result = await client.post("/api/v1/reporting/export", json={"format": "excel"})
        assert result.status_code == 400
        assert "Unsupported format" in result.json()["detail"]

    async def test_filtering_by_date_range(self, client: AsyncClient, db_session, sample_application_data):
        # Create an app today
        app_today = MortgageApplication(**sample_application_data)
        
        # Create an app yesterday
        app_yesterday = MortgageApplication(**{**sample_application_data, "applicant_id": "old_cust"})
        app_yesterday.created_at = app_yesterday.created_at - timedelta(days=2)
        
        db_session.add(app_today)
        db_session.add(app_yesterday)
        await db_session.commit()

        # Filter for last 24 hours
        start_date = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        
        result = await client.get(f"/api/v1/reporting/portfolio-summary?start_date={start_date}")
        assert result.status_code == 200
        
        data = result.json()
        # Should only count the recent one
        assert data["total_applications"] == 1

    async def test_cmhc_insurance_report(self, client: AsyncClient, db_session, sample_application_data):
        # High LTV scenario (>80%)
        high_ltv_data = {**sample_application_data, "property_value": Decimal("460000.00")} # 450k/460k > 97%
        app = MortgageApplication(**high_ltv_data)
        
        db_session.add(app)
        await db_session.commit()

        result = await client.get("/api/v1/reporting/cmhc-stats")
        assert result.status_code == 200
        
        data = result.json()
        assert "insurance_required_count" in data
        assert data["insurance_required_count"] == 1
        # Verify tier calculation logic was executed (e.g. premium tiers)
        assert "total_premium_estimate" in data