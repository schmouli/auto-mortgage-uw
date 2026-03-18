```python
import pytest
from decimal import Decimal
from datetime import datetime, date
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

# Import models and app
from mortgage_underwriting.modules.reporting_analytics.models import Report, ApplicationAggregate
from mortgage_underwriting.modules.reporting_analytics.routes import router
from fastapi import FastAPI

@pytest.mark.integration
@pytest.mark.asyncio
class TestReportingEndpoints:

    async def test_create_report_endpoint_success(self, app, db_session):
        # Arrange
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "report_type": "application_summary",
                "filters": {
                    "start_date": "2023-01-01",
                    "end_date": "2023-01-31"
                },
                "format": "pdf"
            }

            # Act
            response = await client.post("/api/v1/reporting/reports", json=payload)

            # Assert
            assert response.status_code == 201
            data = response.json()
            assert data["id"] > 0
            assert data["status"] == "pending"
            assert "created_at" in data

            # Verify DB state
            stmt = select(Report).where(Report.id == data["id"])
            result = await db_session.execute(stmt)
            report = result.scalar_one()
            assert report is not None
            assert report.report_type == "application_summary"

    async def test_create_report_endpoint_invalid_date_range(self, app):
        # Arrange
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "report_type": "application_summary",
                "filters": {
                    "start_date": "2023-12-31",
                    "end_date": "2023-01-01"
                },
                "format": "pdf"
            }

            # Act
            response = await client.post("/api/v1/reporting/reports", json=payload)

            # Assert
            assert response.status_code == 400
            assert "error_code" in response.json()

    async def test_get_report_endpoint_success(self, app, db_session):
        # Arrange - Create a report directly in DB
        new_report = Report(
            report_type="application_summary",
            status="completed",
            generated_url="http://example.com/report.pdf",
            filters={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(new_report)
        await db_session.commit()
        await db_session.refresh(new_report)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get(f"/api/v1/reporting/reports/{new_report.id}")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == new_report.id
            assert data["status"] == "completed"
            assert data["generated_url"] == "http://example.com/report.pdf"

    async def test_get_report_endpoint_not_found(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get("/api/v1/reporting/reports/99999")

            # Assert
            assert response.status_code == 404

    async def test_list_reports_pagination(self, app, db_session):
        # Arrange - Seed 5 reports
        for i in range(5):
            db_session.add(Report(
                report_type="application_summary",
                status="completed",
                generated_url=f"url_{i}.pdf",
                filters={},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            ))
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get("/api/v1/reporting/reports?limit=2&offset=0")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            assert data["total"] == 5
            assert data["offset"] == 0

@pytest.mark.integration
@pytest.mark.asyncio
class TestAnalyticsEndpoints:

    async def test_get_regional_summary_success(self, app, db_session):
        # Arrange - Seed aggregate data
        agg1 = ApplicationAggregate(
            total_applications=10,
            approved_count=8,
            rejected_count=2,
            total_loan_amount=Decimal("1000000.00"),
            average_ltv=Decimal("75.00"),
            region="ON",
            created_at=datetime.utcnow()
        )
        agg2 = ApplicationAggregate(
            total_applications=5,
            approved_count=4,
            rejected_count=1,
            total_loan_amount=Decimal("500000.00"),
            average_ltv=Decimal("80.00"),
            region="QC",
            created_at=datetime.utcnow()
        )
        db_session.add_all([agg1, agg2])
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get("/api/v1/reporting/analytics/regional-summary")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            
            # Verify Decimal serialization and logic
            on_data = next((item for item in data if item["region"] == "ON"), None)
            assert on_data is not None
            assert on_data["total_applications"] == 10
            assert on_data["total_loan_amount"] == "1000000.00" # JSON string representation

    async def test_get_approval_rates(self, app, db_session):
        # Arrange
        agg = ApplicationAggregate(
            total_applications=100,
            approved_count=80,
            rejected_count=20,
            total_loan_amount=Decimal("0.00"),
            average_ltv=Decimal("0.00"),
            region="ALL",
            created_at=datetime.utcnow()
        )
        db_session.add(agg)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get("/api/v1/reporting/analytics/approval-rates")

            # Assert
            assert response.status_code == 200
            data = response.json()
            # Assuming endpoint returns a list of rates or a summary object
            # Testing that it returns valid JSON
            assert isinstance(data, list) or isinstance(data, dict)

    async def test_export_analytics_csv(self, app, db_session):
        # Arrange
        agg = ApplicationAggregate(
            total_applications=1,
            approved_count=1,
            rejected_count=0,
            total_loan_amount=Decimal("100.00"),
            average_ltv=Decimal("50.00"),
            region="AB",
            created_at=datetime.utcnow()
        )
        db_session.add(agg)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get(
                "/api/v1/reporting/analytics/export",
                params={"format": "csv", "type": "regional_summary"}
            )

            # Assert
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/csv; charset=utf-8"
            # Verify content contains headers
            content = response.text
            assert "region" in content.lower()
            assert "AB" in content
```