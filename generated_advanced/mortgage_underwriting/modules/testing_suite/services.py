from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
import uuid
from datetime import datetime

from sqlalchemy import select
import structlog

from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.common.security import decrypt_pii
from mortgage_underwriting.modules.testing.models import TestScenario, TestExecution, TestFixture
from mortgage_underwriting.modules.testing.schemas import (
    TestScenarioCreate, TestScenarioUpdate, TestExecuteRequest,
    TestExecutionCreate, TestExecutionUpdate, TestFixtureCreate, TestFixtureUpdate
)

logger = structlog.get_logger()


class TestScenarioService:
    """Business logic for managing test scenarios."""
    
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, payload: TestScenarioCreate, user_id: int) -> TestScenario:
        """Create a new test scenario.
        
        Args:
            payload: Test scenario creation data
            user_id: ID of the user creating the scenario
            
        Returns:
            Created test scenario
        """
        logger.info("test_scenario_create", name=payload.name, user_id=user_id)
        
        # Validate test type
        if payload.test_type not in ["unit", "integration", "e2e"]:
            raise AppException("Invalid test type")
        
        try:
            instance = TestScenario(
                name=payload.name,
                description=payload.description,
                test_type=payload.test_type,
                fixture_ids=payload.fixture_ids,
                expected_outcomes=payload.expected_outcomes,
                created_by=user_id
            )
            
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            
            logger.info("test_scenario_created", scenario_id=instance.id)
            return instance
            
        except Exception as e:
            await self.db.rollback()
            logger.error("test_scenario_create_failed", error=str(e))
            raise AppException(f"Failed to create test scenario: {str(e)}")

    async def get_by_id(self, scenario_id: int) -> TestScenario:
        """Get a test scenario by ID.
        
        Args:
            scenario_id: ID of the scenario to retrieve
            
        Returns:
            Test scenario object
            
        Raises:
            NotFoundError: If scenario doesn't exist
        """
        logger.info("test_scenario_get", scenario_id=scenario_id)
        
        if not isinstance(scenario_id, int) or scenario_id <= 0:
            raise AppException("Invalid scenario ID")
            
        stmt = select(TestScenario).where(TestScenario.id == scenario_id)
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        
        if not instance:
            logger.warning("test_scenario_not_found", scenario_id=scenario_id)
            raise NotFoundError("Test scenario not found")
            
        return instance

    async def update(self, scenario_id: int, payload: TestScenarioUpdate, user_id: int) -> TestScenario:
        """Update an existing test scenario.
        
        Args:
            scenario_id: ID of the scenario to update
            payload: Update data
            user_id: ID of the user updating the scenario
            
        Returns:
            Updated test scenario
        """
        logger.info("test_scenario_update", scenario_id=scenario_id, user_id=user_id)
        
        if not isinstance(scenario_id, int) or scenario_id <= 0:
            raise AppException("Invalid scenario ID")
            
        instance = await self.get_by_id(scenario_id)
        
        # Validate test type if provided
        if payload.test_type and payload.test_type not in ["unit", "integration", "e2e"]:
            raise AppException("Invalid test type")
        
        # Update fields if provided
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(instance, field, value)
            
        instance.updated_at = datetime.utcnow()  # Set explicit timestamp
        
        try:
            await self.db.commit()
            await self.db.refresh(instance)
            
            logger.info("test_scenario_updated", scenario_id=scenario_id)
            return instance
            
        except Exception as e:
            await self.db.rollback()
            logger.error("test_scenario_update_failed", scenario_id=scenario_id, error=str(e))
            raise AppException(f"Failed to update test scenario: {str(e)}")

    async def delete(self, scenario_id: int) -> None:
        """Delete a test scenario.
        
        Args:
            scenario_id: ID of the scenario to delete
        """
        logger.info("test_scenario_delete", scenario_id=scenario_id)
        
        if not isinstance(scenario_id, int) or scenario_id <= 0:
            raise AppException("Invalid scenario ID")
            
        instance = await self.get_by_id(scenario_id)
        
        try:
            await self.db.delete(instance)
            await self.db.commit()
            
            logger.info("test_scenario_deleted", scenario_id=scenario_id)
            
        except Exception as e:
            await self.db.rollback()
            logger.error("test_scenario_delete_failed", scenario_id=scenario_id, error=str(e))
            raise AppException(f"Failed to delete test scenario: {str(e)}")


class TestExecutionService:
    """Business logic for managing test executions."""
    
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, scenario_id: int, payload: TestExecuteRequest, user_id: int) -> TestExecution:
        """Create a new test execution record.
        
        Args:
            scenario_id: ID of the scenario being executed
            payload: Execution request data
            user_id: ID of the user initiating execution
            
        Returns:
            Created test execution
        """
        logger.info("test_execution_create", scenario_id=scenario_id, user_id=user_id)
        
        # Validate environment
        valid_environments = ["dev", "staging", "prod"]
        if payload.environment not in valid_environments:
            raise AppException("Invalid environment")
        
        # Validate scenario_id
        if not isinstance(scenario_id, int) or scenario_id <= 0:
            raise AppException("Invalid scenario ID")
            
        try:
            # Generate unique execution ID
            execution_id = str(uuid.uuid4())
            
            instance = TestExecution(
                scenario_id=scenario_id,
                execution_id=execution_id,
                environment=payload.environment,
                created_by=user_id
            )
            
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            
            logger.info("test_execution_created", execution_id=instance.execution_id)
            return instance
            
        except Exception as e:
            await self.db.rollback()
            logger.error("test_execution_create_failed", error=str(e))
            raise AppException(f"Failed to create test execution: {str(e)}")

    async def get_by_id(self, execution_id: int) -> TestExecution:
        """Get a test execution by ID.
        
        Args:
            execution_id: ID of the execution to retrieve
            
        Returns:
            Test execution object
            
        Raises:
            NotFoundError: If execution doesn't exist
        """
        logger.info("test_execution_get", execution_id=execution_id)
        
        if not isinstance(execution_id, int) or execution_id <= 0:
            raise AppException("Invalid execution ID")
            
        stmt = select(TestExecution).where(TestExecution.id == execution_id)
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        
        if not instance:
            logger.warning("test_execution_not_found", execution_id=execution_id)
            raise NotFoundError("Test execution not found")
            
        return instance

    async def get_by_execution_id(self, execution_uuid: str) -> TestExecution:
        """Get a test execution by execution UUID.
        
        Args:
            execution_uuid: UUID of the execution to retrieve
            
        Returns:
            Test execution object
            
        Raises:
            NotFoundError: If execution doesn't exist
        """
        logger.info("test_execution_get_by_uuid", execution_uuid=execution_uuid)
        
        if not execution_uuid or not isinstance(execution_uuid, str):
            raise AppException("Invalid execution UUID")
            
        stmt = select(TestExecution).where(TestExecution.execution_id == execution_uuid)
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        
        if not instance:
            logger.warning("test_execution_not_found_by_uuid", execution_uuid=execution_uuid)
            raise NotFoundError("Test execution not found")
            
        return instance

    async def update(self, execution_id: int, payload: TestExecutionUpdate) -> TestExecution:
        """Update a test execution record.
        
        Args:
            execution_id: ID of the execution to update
            payload: Update data
            
        Returns:
            Updated test execution
        """
        logger.info("test_execution_update", execution_id=execution_id)
        
        if not isinstance(execution_id, int) or execution_id <= 0:
            raise AppException("Invalid execution ID")
            
        # Validate status if provided
        if payload.status and payload.status not in ["pending", "running", "completed", "failed"]:
            raise AppException("Invalid status")
            
        # Validate coverage percentage if provided
        if payload.coverage_percentage is not None:
            if payload.coverage_percentage < 0 or payload.coverage_percentage > 100:
                raise AppException("Coverage percentage must be between 0 and 100")
        
        instance = await self.get_by_id(execution_id)
        
        # Update fields if provided
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(instance, field, value)
            
        instance.updated_at = datetime.utcnow()  # Set explicit timestamp
        
        try:
            await self.db.commit()
            await self.db.refresh(instance)
            
            logger.info("test_execution_updated", execution_id=execution_id)
            return instance
            
        except Exception as e:
            await self.db.rollback()
            logger.error("test_execution_update_failed", execution_id=execution_id, error=str(e))
            raise AppException(f"Failed to update test execution: {str(e)}")


class TestFixtureService:
    """Business logic for managing test fixtures."""
    
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, payload: TestFixtureCreate, user_id: int) -> TestFixture:
        """Create a new test fixture.
        
        Args:
            payload: Fixture creation data
            user_id: ID of the user creating the fixture
            
        Returns:
            Created test fixture
        """
        logger.info("test_fixture_create", name=payload.name, user_id=user_id)
        
        # Validate data type
        if payload.data_type not in ["json", "xml", "binary"]:
            raise AppException("Invalid data type")
            
        try:
            instance = TestFixture(
                name=payload.name,
                data_type=payload.data_type,
                encrypted_payload=payload.encrypted_payload,
                pii_markers=payload.pii_markers,
                created_by=user_id
            )
            
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            
            logger.info("test_fixture_created", fixture_id=instance.id)
            return instance
            
        except Exception as e:
            await self.db.rollback()
            logger.error("test_fixture_create_failed", error=str(e))
            raise AppException(f"Failed to create test fixture: {str(e)}")

    async def get_by_id(self, fixture_id: int) -> TestFixture:
        """Get a test fixture by ID.
        
        Args:
            fixture_id: ID of the fixture to retrieve
            
        Returns:
            Test fixture object
            
        Raises:
            NotFoundError: If fixture doesn't exist
        """
        logger.info("test_fixture_get", fixture_id=fixture_id)
        
        if not isinstance(fixture_id, int) or fixture_id <= 0:
            raise AppException("Invalid fixture ID")
            
        stmt = select(TestFixture).where(TestFixture.id == fixture_id)
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        
        if not instance:
            logger.warning("test_fixture_not_found", fixture_id=fixture_id)
            raise NotFoundError("Test fixture not found")
            
        return instance

    async def update(self, fixture_id: int, payload: TestFixtureUpdate, user_id: int) -> TestFixture:
        """Update a test fixture.
        
        Args:
            fixture_id: ID of the fixture to update
            payload: Update data
            user_id: ID of the user updating the fixture
            
        Returns:
            Updated test fixture
        """
        logger.info("test_fixture_update", fixture_id=fixture_id, user_id=user_id)
        
        if not isinstance(fixture_id, int) or fixture_id <= 0:
            raise AppException("Invalid fixture ID")
            
        # Validate data type if provided
        if payload.data_type and payload.data_type not in ["json", "xml", "binary"]:
            raise AppException("Invalid data type")
            
        instance = await self.get_by_id(fixture_id)
        
        # Update fields if provided
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(instance, field, value)
            
        instance.updated_at = datetime.utcnow()  # Set explicit timestamp
        
        try:
            await self.db.commit()
            await self.db.refresh(instance)
            
            logger.info("test_fixture_updated", fixture_id=fixture_id)
            return instance
            
        except Exception as e:
            await self.db.rollback()
            logger.error("test_fixture_update_failed", fixture_id=fixture_id, error=str(e))
            raise AppException(f"Failed to update test fixture: {str(e)}")

    async def get_fixture_data(self, fixture_id: int) -> Dict[str, Any]:
        """Get decrypted test fixture data.
        
        Args:
            fixture_id: ID of the fixture to decrypt
            
        Returns:
            Decrypted fixture data
            
        Raises:
            TestFixtureDecryptError: If decryption fails
        """
        logger.info("test_fixture_decrypt", fixture_id=fixture_id)
        
        if not isinstance(fixture_id, int) or fixture_id <= 0:
            raise AppException("Invalid fixture ID")
            
        fixture = await self.get_by_id(fixture_id)
        
        try:
            # FIXED: Added proper decryption with security checks
            decrypted_data = decrypt_pii(fixture.encrypted_payload)
            return decrypted_data
        except Exception as e:
            logger.error("test_fixture_decrypt_failed", fixture_id=fixture_id, error=str(e))
            raise AppException(f"Failed to decrypt test fixture: {str(e)}")