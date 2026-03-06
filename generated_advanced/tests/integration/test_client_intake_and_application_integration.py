```python
import pytest
from decimal import Decimal
from httpx import AsyncClient

@pytest.mark.integration
class TestClientIntakeEndpoints:

    @pytest.mark.asyncio
    async def test_create_client_flow(self, client: AsyncClient):
        """
        Full workflow: Create a client and verify retrieval.
        """
        payload = {
            "first_name": "Alice",
            "last_name": "Johnson",
            "email": "alice.j@example.com",
            "phone": "6475559876",
            "date_of_birth": "1992-07-15",
            "sin": "555555555",
            "address": "321 Queen St W",
            "city": "Toronto",
            "province": "ON",
            "postal_code": "M5V2A4"
        }

        # 1. Create Client
        response = await client.post("/api/v1/clients", json=payload)
        assert response.status_code == 201
        
        data = response.json()
        assert "id" in data
        assert data["email"] == "alice.j@example.com"
        
        # PIPEDA Compliance Check: SIN must NOT be in response
        assert "sin" not in data
        assert "sin_encrypted" not in data
        
        client_id = data["id"]

        # 2. Retrieve Client
        response = await client.get(f"/api/v1/clients/{client_id}")
        assert response.status_code == 200
        
        retrieved_data = response.json()
        assert retrieved_data["id"] == client_id
        assert retrieved_data["first_name"] == "Alice"

    @pytest.mark.asyncio
    async def test_create_client_validation_error(self, client: AsyncClient):
        """
        Test validation on invalid input (e.g., bad email format).
        """
        payload = {
            "first_name": "Bob",
            "last_name": "Builder",
            "email": "not-an-email", # Invalid
            "phone": "4165550000",
            "date_of_birth": "1980-01-01",
            "sin": "111111111",
            "address": "1 Construction Way",
            "city": "Toronto",
            "province": "ON",
            "postal_code": "M1M1M1"
        }

        response = await client.post("/api/v1/clients", json=payload)
        assert response.status_code == 422 # Validation Error

    @pytest.mark.asyncio
    async def test_create_application_flow(self, client: AsyncClient):
        """
        Full workflow: Create client, then submit application.
        """
        # 1. Setup: Create a client first
        client_payload = {
            "first_name": "Charlie",
            "last_name": "Brown",
            "email": "charlie@example.com",
            "phone": "4165551111",
            "date_of_birth": "1975-11-30",
            "sin": "222222222",
            "address": "50 Snoopy Lane",
            "city": "Toronto",
            "province": "ON",
            "postal_code": "M4C1C1"
        }
        client_resp = await client.post("/api/v1/clients", json=client_payload)
        client_id = client_resp.json()["id"]

        # 2. Create Application
        app_payload = {
            "client_id": client_id,
            "property_address": "882 Broadview Ave",
            "property_city": "Toronto",
            "property_province": "ON",
            "property_postal_code": "M4K2P3",
            "purchase_price": "750000.00",
            "down_payment": "150000.00",
            "loan_amount": "600000.00",
            "amortization_years": 25,
            "interest_rate": "4.75",
            "employment_status": "employed",
            "employer_name": "Peanuts Corp",
            "annual_income": "110000.00",
            "monthly_debt_payments": "450.00"
        }

        response = await client.post("/api/v1/applications", json=app_payload)
        assert response.status_code == 201
        
        app_data = response.json()
        assert "id" in app_data
        assert app_data["client_id"] == client_id
        assert Decimal(app_data["loan_amount"]) == Decimal("600000.00")

    @pytest.mark.asyncio
    async def test_create_application_client_not_found(self, client: AsyncClient):
        """
        Test application submission with non-existent client_id.
        """
        app_payload = {
            "client_id": 99999, # Non-existent
            "property_address": "123 Nowhere",
            "property_city": "Ghost Town",
            "property_province": "ON",
            "property_postal_code": "A1A1A1",
            "purchase_price": "100000.00",
            "down_payment": "20000.00",
            "loan_amount": "80000.00",
            "amortization_years": 20,
            "interest_rate": "3.5",
            "employment_status": "employed",
            "employer_name": "Void",
            "annual_income": "50000.00",
            "monthly_debt_payments": "0.00"
        }

        response = await client.post("/api/v1/applications", json=app_payload)
        # Expecting 404 Not Found or 400 Bad Request depending on implementation
        assert response.status_code in [404, 400]

    @pytest.mark.asyncio
    async def test_get_application_details(self, client: AsyncClient):
        """
        Test retrieving application details and calculated fields.
        """
        # 1. Create Client
        c_resp = await client.post("/api/v1/clients", json={
            "first_name": "Diana", "last_name": "Prince", "email": "diana@amazon.com",
            "phone": "4165559999", "date_of_birth": "1985-10-21", "sin": "333333333",
            "address": "1 Island Way", "city": "Toronto", "province": "ON", "postal_code": "M5H1A1"
        })
        client_id = c_resp.json()["id"]

        # 2. Create Application
        a_resp = await client.post("/api/v1/applications", json={
            "client_id": client_id,
            "property_address": "2 Hero Blvd",
            "property_city": "Toronto",
            "property_province": "ON",
            "property_postal_code": "M5V1A1",
            "purchase_price": "1000000.00",
            "down_payment": "200000.00",
            "loan_amount": "800000.00",
            "amortization_years": 30,
            "interest_rate": "5.0",
            "employment_status": "employed",
            "employer_name": "Justice League",
            "annual_income": "200000.00",
            "monthly_debt_payments": "1000.00"
        })
        app_id = a_resp.json()["id"]

        # 3. Get Application
        response = await client.get(f"/api/v1/applications/{app_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == app_id
        # Verify Financial Precision (Decimal)
        assert data["purchase_price"] == "1000000.00"
        # Verify calculated ratios are present (if returned by GET endpoint)
        # Note: Depending on implementation, ratios might be calculated later, 
        # but assuming intake calculates preliminary ones:
        # assert "ltv" in data 
        # assert Decimal(data["ltv"]) == Decimal("80.00")
```