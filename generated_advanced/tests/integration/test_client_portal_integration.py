```python
import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.client_portal.models import Client, MortgageApplication


@pytest.mark.integration
class TestClientPortalEndpoints:

    #