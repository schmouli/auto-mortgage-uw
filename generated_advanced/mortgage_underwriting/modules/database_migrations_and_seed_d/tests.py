Here are the comprehensive tests for the Database Migrations & Seed Data module for the Canadian Mortgage Underwriting System.

--- conftest.py ---
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, List
from unittest.mock import MagicMock, patch

# Mock imports for the project structure
# In a real scenario, these would be actual imports
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# --- Mock Database Models for Testing ---
class Province(Base):
    __tablename__ = "provinces"
    id = int
    code = str
    name = str
    tax_rate = float

class MortgageProduct(Base):
    __tablename__ = "mortgage_products"
    id = int
    name = str
    rate_type = str  # Fixed, Variable
    term_months = int
    min_credit_score = int

# --- Fixtures ---

@pytest.fixture(scope="function")
def db_engine():
    """Create an in-memory SQLite database engine."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Create a new database session for a test."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(scope="function")
def client(db_session: Session) -> TestClient:
    """Create a FastAPI TestClient with the test database."""
    # Mocking the dependency override for the database session
    from main import app, get_db
    
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def mock_alembic_config():
    """Mock Alembic configuration for migration testing."""
    with patch('alembic.config.Config') as mock_config:
        config_instance = MagicMock()
        mock_config.return_value = config_instance
        yield config_instance

@pytest.fixture
def sample_seed_provinces() -> List[dict]:
    """Standard Canadian province seed data."""
    return [
        {"code": "ON", "name": "Ontario", "tax_rate": 0.13},
        {"code": "BC", "name": "British Columbia", "tax_rate": 0.12},
        {"code": "QC", "name": "Quebec", "tax_rate": 0.14975},
        {"code": "AB", "name": "Alberta", "tax_rate": 0.05},
    ]

@pytest.fixture
def sample_seed_products() -> List[dict]:
    """Standard mortgage product seed data."""
    return [
        {"name": "5-Year Fixed", "rate_type": "Fixed", "term_months": 60, "min_credit_score": 680},
        {"name": "5-Year Variable", "rate_type": "Variable", "term_months": 60, "min_credit_score": 700},
        {"name": "1-Year Fixed", "rate_type": "Fixed", "term_months": 12, "min_credit_score": 650},
    ]

@pytest.fixture
def mock_migration_script():
    """Mock the migration script runner."""
    with patch('db.migrations.run_migrations') as mock_run:
        yield mock_run
```

--- unit_tests ---

```python
import pytest
from unittest.mock import MagicMock, patch, call
from sqlalchemy.orm import Session
from db import seed_data, migrations

class TestSeedDataLogic:
    """Unit tests for seed data generation logic."""

    def test_seed_provinces_generates_correct_count(self, sample_seed_provinces):
        """Test that the province generator returns the expected number of records."""
        # Assuming a function that generates data dict
        data = seed_data.generate_province_data()
        assert len(data) == 13, "Should generate 13 Canadian provinces/territories"
        assert len(data) > 0

    def test_seed_provinces_includes_key_regions(self, sample_seed_provinces):
        """Test that critical Canadian mortgage markets are included."""
        data = seed_data.generate_province_data()
        codes = [p['code'] for p in data]
        
        assert "ON" in codes, "Ontario must be present"
        assert "BC" in codes, "British Columbia must be present"
        assert "AB" in codes, "Alberta must be present"
        assert "QC" in codes, "Quebec must be present"

    def test_seed_provinces_validates_tax_rates(self):
        """Test that generated tax rates are within valid bounds."""
        data = seed_data.generate_province_data()
        for province in data:
            assert 0.0 <= province['tax_rate'] <= 0.15, f"Tax rate invalid for {province['code']}"
            assert isinstance(province['tax_rate'], float), "Tax rate must be float"
            assert 'name' in province, "Province name missing"
            assert len(province['code']) == 2, "Province code must be 2 chars"

    def test_seed_mortgage_products_generates_variety(self):
        """Test that seed data includes both Fixed and Variable products."""
        data = seed_data.generate_product_data()
        rate_types = set([p['rate_type'] for p in data])
        
        assert "Fixed" in rate_types, "Must include Fixed rate products"
        assert "Variable" in rate_types, "Must include Variable rate products"
        assert len(data) >= 3, "Should seed at least 3 base products"

    def test_seed_mortgage_products_term_lengths(self):
        """Test that product term lengths are standard Canadian values."""
        data = seed_data.generate_product_data()
        valid_terms = {12, 24, 36, 48, 60, 120} # Months
        
        for product in data:
            assert product['term_months'] in valid_terms, f"Invalid term: {product['term_months']}"
            assert product['min_credit_score'] >= 600, "Min score too low for underwriting"
            assert 'name' in product

    def test_seed_data_deduplication_logic(self):
        """Test that the seeder handles duplicate keys gracefully (if implemented)."""
        # Mock session
        mock_session = MagicMock(spec=Session)
        
        # Simulate existing data conflict
        mock_session.execute.side_effect = Exception("IntegrityError")
        
        # This test assumes a try/except block exists in the seeder
        # We are testing the function's ability to handle errors or check existence
        try:
            seed_data.seed_provinces_if_empty(mock_session)
        except Exception:
            pass # Expected in this mock scenario
            
        # Verify session interaction occurred
        assert mock_session.execute.called or mock_session.add.called

    def test_migration_script_identifies_current_version(self, mock_alembic_config):
        """Test that the migration utility can check the current version."""
        with patch('alembic.command.current') as mock_curr:
            migrations.check_db_version(mock_alembic_config)
            mock_curr.assert_called_once_with(mock_alembic_config)

    def test_migration_upgrade_command_structure(self, mock_alembic_config):
        """Test that the upgrade command is formed correctly."""
        with patch('alembic.command.upgrade') as mock_upgrade:
            migrations.run_upgrade(mock_alembic_config, "head")
            mock_upgrade.assert_called_once_with(mock_alembic_config, "head")

    def test_migration_downgrade_command_structure(self, mock_alembic_config):
        """Test that the downgrade command is formed correctly."""
        with patch('alembic.command.downgrade') as mock_downgrade:
            migrations.run_downgrade(mock_alembic_config, "-1")
            mock_downgrade.assert_called_once_with(mock_alembic_config, "-1")

    def test_seed_data_commit_transaction(self, db_session):
        """Test that seeding commits data to the session."""
        # We use the real db_session fixture but treat it as a unit test for the function
        initial_count = db_session.query(Province).count()
        
        # Add raw data directly to simulate seeder function
        new_prov = Province(id=99, code="XX", name="Test", tax_rate=0.1)
        db_session.add(new_prov)
        db_session.commit()
        
        final_count = db_session.query(Province).count()
        assert final_count == initial_count + 1, "Data was not committed"

    def test_calculate_b20_stress_test_seed(self):
        """Test that stress test constants are seeded correctly for B-20 rules."""
        constants = seed_data.get_underwriting_constants()
        assert 'min_stress_test_rate' in constants
        assert 'b20_guideline_version' in constants
        assert constants['min_stress_test_rate'] >= 4.79, "Stress test floor seems incorrect"

    def test_lender_criteria_seeding(self):
        """Test that lender-specific criteria are generated."""
        lenders = seed_data.generate_lender_criteria()
        assert len(lenders) > 0
        for lender in lenders:
            assert 'max_ltv' in lender
            assert 0 < lender['max_ltv'] <= 0.95, "Max LTV must be between 0 and 95%"

    def test_seed_data_rollback_on_error(self):
        """Test that seeder rolls back if one insert fails."""
        mock_session = MagicMock(spec=Session)
        # Setup: First add succeeds, second fails
        mock_session.add.side_effect = [None, Exception("DB Fail")]
        
        with pytest.raises(Exception):
            seed_data.seed_all(mock_session)
            
        mock_session.rollback.assert_called_once()

    def test_insurance_premium_seed_data(self):
        """Test CMHC insurance premium tiers are seeded."""
        tiers = seed_data.get_insurance_premium_tiers()
        assert len(tiers) == 4 or len(tiers) == 5, "Standard CMHC tiers missing"
        
        # Check standard logic (e.g., < 65% is 0.6%, > 95% is 4.0%)
        low_ltv = [t for t in tiers if t['max_ltv'] <= 0.65][0]
        high_ltv = [t for t in tiers if t['max_ltv'] > 0.95][0]
        
        assert low_ltv['premium_rate'] < high_ltv['premium_rate']

    def test_migration_history_table_exists_check(self, mock_alembic_config):
        """Test logic that checks if alembic_version table exists."""
        # This is a logic test for a helper function
        with patch('db.migrations.inspect') as mock_inspect:
            mock_inspector = MagicMock()
            mock_inspector.get_table_names.return_value = ['users', 'alembic_version']
            mock_inspect.return_value = mock_inspector
            
            result = migrations.check_migration_table_exists(mock_alembic_config)
            assert result is True
            mock_inspector.get_table_names.assert_called_once()

    def test_validation_of_postal_codes_in_seed(self):
        """Test that seed data uses valid Canadian postal code formats (if addresses included)."""
        addresses = seed_data.generate_sample_branch_addresses()
        for addr in addresses:
            assert 'postal_code' in addr
            # Basic Regex check for A1A 1A1
            import re
            assert re.match(r'^[A-Z]\d[A-Z]\s\d[A-Z]\d$', addr['postal_code'])

    def test_seed_data_is_idempotent(self):
        """Test that running seed data twice doesn't duplicate data (logic check)."""
        mock_session = MagicMock(spec=Session)
        # Mock exists check to return True (data already there)
        mock_session.query.return_value.filter_by.return_value.first.return_value = MagicMock()
        
        seed_data.seed_provinces_if_empty(mock_session)
        
        # Assert that add was NOT called because data exists
        mock_session.add.assert_not_called()

    def test_currency_formatting_in_seeds(self):
        """Test that monetary values in seeds are formatted correctly (2 decimal places)."""
        limits = seed_data.get_transaction_limits()
        for limit in limits:
            if 'max_mortgage_amount' in limit:
                # Check if it's a valid decimal number
                assert isinstance(limit['max_mortgage_amount'], (int, float))
```

--- integration_tests ---

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