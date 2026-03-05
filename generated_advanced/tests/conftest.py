import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from unittest.mock import AsyncMock, MagicMock

# Assuming module name is 'client_intake'
from mortgage_underwriting.modules.client_intake.models import Client, Application
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.client_intake.schemas import (
    ClientCreate,
    ApplicationCreate,
    EmploymentInfo,
    AssetInfo
)

# Pytest Async Configuration
pytest_plugins = ('pytest_asyncio',)

#