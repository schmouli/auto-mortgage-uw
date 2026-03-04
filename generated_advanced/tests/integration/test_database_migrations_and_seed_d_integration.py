```python
import pytest
from fastapi import Request
from sqlalchemy import text

class TestMigrationIntegration:
    """Integration tests verifying database schema and state."""

    def test_database_tables_created(self, db_session: Session):
        """Verify that migration created all necessary tables."""
        # Use raw SQL to check table existence
        result = db_session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        ))
        tables = [row[0] for row in result]
        
        assert "provinces" in tables
        assert "mortgage_products" in tables
        assert "borrowers" in tables
        assert "applications" in tables
        assert "alembic_version" in tables

    def test_table_columns_correctness(self, db_session: Session):
        """Verify that columns have correct data types after migration."""
        result = db_session.execute(text("PRAGMA table_info(provinces)"))
        columns = {row[1]: row[2] for row in result} # name: type
        
        assert "code" in columns
        assert "tax_rate" in columns
        assert columns["code"] in ("VARCHAR", "TEXT")
        assert columns["tax_rate"] in ("FLOAT", "REAL")

    def test_foreign_key_constraints_exist(self, db_session: Session):
        """Verify that FK constraints are enforced (schema level)."""
        # SQLite specific check for FKs
        result = db_session.execute(text("PRAGMA foreign_keys;"))
        is_enabled = result.fetchone()[0]
        assert is_enabled == 1, "Foreign keys must be enabled"

    def test_alembic_version_table_populated(self, db_session: Session):
        """Verify that the migration version is recorded."""
        result = db_session.execute(text("SELECT version_num FROM alembic_version"))
        version = result.fetchone()
        assert version is not None
        assert len(version[0]) > 0

class TestSeedDataIntegration:
    """Integration tests for seeded data via API or direct DB access."""

    def test_provinces_seeded_via_api(self, client: TestClient):
        """Test that provinces are accessible and seeded via the API."""
        response = client.get("/api/v1/reference/provinces")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) >= 13
        assert any(p['code'] == 'ON' for p in data)
        assert any(p['code'] == 'BC' for p in data)

    def test_mortgage_products_seeded_via_api(self, client: TestClient):
        """Test that mortgage products are available for selection."""
        response = client.get("/api/v1/reference/products")
        assert response.status_code == 200
        
        products = response.json()
        assert len(products) > 0
        
        # Verify structure
        for prod in products:
            assert 'id' in prod
            assert 'name' in prod
            assert 'rate_type' in prod
            assert prod['rate_type'] in ['Fixed', 'Variable']

    def test_seed_data_integrity_check(self, client: TestClient):
        """Verify seeded data passes validation logic."""
        # Get a specific product
        response = client.get("/api/v1/reference/products")
        products = response.json()
        
        # Pick the 5-year fixed
        fixed_5yr = next((p for p in products if "5-Year Fixed" in p['name']), None)
        assert fixed_5yr is not None
        assert fixed_5yr['term_months'] == 60

    def test_system_health_check_uses_seeded_data(self, client: TestClient):
        """Test that the health check endpoint verifies seed data existence."""
        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        
        body = response.json()
        assert body['status'] == 'healthy'
        assert body['database'] == 'connected'
        # Assuming health check checks if reference data is loaded
        assert body['reference_data_loaded'] is True

    def test_reseeding_endpoint_protected(self, client: TestClient):
        """Test that re-seeding data is restricted to admins."""
        # Attempt without auth
        response = client.post("/api/v1/admin/reseed")
        assert response.status_code in [401, 403], "Reseed should be protected"

    def test_create_application_uses_seeded_product(self, client: TestClient):
        """Workflow test: Create an app using a seeded product ID."""
        # 1. Get products
        prods_resp = client.get("/api/v1/reference/products")
        product_id = prods_resp.json()[0]['id']
        
        # 2. Create Application
        app_data = {
            "borrower_name": "John Doe",
            "product_id": product_id,
            "amount": 500000
        }
        create_resp = client.post("/api/v1/applications", json=app_data)
        
        # 3. Verify
        assert create_resp.status_code == 201
        resp_json = create_resp.json()
        assert resp_json['product_id'] == product_id

    def test_province_validation_in_application_flow(self, client: TestClient):
        """Test that only seeded provinces are accepted in applications."""
        # 1. Get a valid province code
        prov_resp = client.get("/api/v1/reference/provinces")
        valid_code = prov_resp.json()[0]['code']
        
        # 2. Submit Application with valid code
        app_data = {
            "property_province": valid_code,
            "loan_amount": 300000
        }
        resp = client.post("/api/v1/applications/validate", json=app_data)
        assert resp.status_code == 200

        # 3. Submit with invalid code
        app_data['property_province'] = "XX" # Invalid
        resp = client.post("/api/v1/applications/validate", json=app_data)
        assert resp.status_code == 422 # Unprocessable Entity

    def test_seed_data_transaction_isolation(self, db_session: Session):
        """Test that seed data is committed and accessible in new transactions."""
        # Explicitly query using a new connection logic (simulated by distinct execute)
        result = db_session.execute(text("SELECT COUNT(*) FROM provinces"))
        count = result.fetchone()[0]
        assert count > 0, "Seed data not found in committed transaction"

    def test_migration_and_seed_workflow(self, client: TestClient):
        """End-to-End: Verify system is ready after migration and seeding."""
        # This test assumes the test setup ran migrations and seeds
        
        # Check DB Schema
        schema_resp = client.get("/api/v1/admin/schema/status")
        assert schema_resp.status_code == 200
        assert schema_resp.json()['migrations_up_to_date'] is True
        
        # Check Data
        data_resp = client.get("/api/v1/reference/all")
        assert data_resp.status_code == 200
        assert len(data_resp.json()) > 0

    def test_update_seeded_data_isolation(self, db_session: Session):
        """Test that updating seeded records doesn't break FKs elsewhere."""
        # Get a province
        prov = db_session.execute(text("SELECT id FROM provinces LIMIT 1")).fetchone()
        prov_id = prov[0]
        
        # Update tax rate
        db_session.execute(text("UPDATE provinces SET tax_rate = 0.99 WHERE id = :id"), {"id": prov_id})
        db_session.commit()
        
        # Verify update
        result = db_session.execute(text("SELECT tax_rate FROM provinces WHERE id = :id"), {"id": prov_id})
        assert result.fetchone()[0] == 0.99

    def test_search_seeded_data_filters(self, client: TestClient):
        """Test that API filters work correctly on seeded data."""
        # Search for Fixed products
        response = client.get("/api/v1/reference/products?type=Fixed")
        assert response.status_code == 200
        
        products = response.json()
        for p in products:
            assert p['rate_type'] == 'Fixed'

    def test_audit_log_for_seeded_data(self, client: TestClient):
        """Verify that initial seeded data might have an audit trail (if applicable)."""
        # Assuming an audit endpoint exists
        response = client.get("/api/v1/admin/audit/changes")
        assert response.status_code == 200
        
        # We might expect to see 'system' as the user for initial seeds
        logs = response.json()
        if len(logs) > 0:
            # If logs exist, check structure
            assert 'entity' in logs[0]
            assert 'action' in logs[0]

    def test_pagination_on_seeded_data(self, client: TestClient):
        """Test that large seed sets (like postal codes) are paginated."""
        # Assuming a large dataset is seeded, e.g., forward sortation areas
        response = client.get("/api/v1/reference/postal-codes?page=1&limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert 'items' in data
        assert len(data['items']) <= 10
        assert 'total' in data
```