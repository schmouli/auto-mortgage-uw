```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_portal.services import ClientPortalService
from mortgage_underwriting.modules.client_portal.schemas import (
    ApplicationCreate,
    ApplicationResponse,
    ClientCreate,
)
from mortgage_underwriting.modules.client_portal.exceptions import (
    ApplicationSubmissionError,
    DuplicateClientError,
)
from mortgage_underwriting.common.exceptions import AppException

# Import Models for type hinting if needed, though service returns schemas/dicts
from mortgage_underwriting.modules.client_portal.models import MortgageApplication


@pytest.mark.unit
class TestClientPortalService:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        db.get = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return ClientPortalService(mock_db)

    #