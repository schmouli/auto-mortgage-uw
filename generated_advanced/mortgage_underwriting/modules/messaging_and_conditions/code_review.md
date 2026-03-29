```json
{
  "status": "BLOCKED",
  "issues": [
    {
      "severity": "critical",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/messaging_conditions/services.py",
      "line": 140,
      "description": "Incomplete code: 'result = await db.exe' is truncated, causing syntax error and broken functionality in update_condition_status method",
      "suggested_fix": "Complete the statement and method implementation:\n```python\nresult = await self.db.execute(stmt)\nawait self.db.commit()\n\nif result.rowcount == 0:\n    raise NotFoundError(detail=\"Condition not found\", error_code=\"CONDITION_001\")\n\n# Fetch updated condition\nquery = select(Condition).where(Condition.id == condition_id)\nresult = await self.db.execute(query)\ncondition = result.scalar_one_or_none()\n\nif not condition:\n    raise NotFoundError(detail=\"Condition not found after update\", error_code=\"CONDITION_001\")\n    \nreturn condition\n```"
    },
    {
      "severity": "critical",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/messaging_conditions/models.py",
      "line": 32,
      "description": "Missing updated_at audit field on Message model violates project convention 'ALWAYS include created_at, updated_at audit fields on every model' and FINTRAC immutability requirements",
      "suggested_fix": "Add updated_at field to Message model:\n```python\nupdated_at: Mapped[datetime] = mapped_column(\n    DateTime(timezone=True), \n    server_default=func.now(), \n    onupdate=func.now(), \n    nullable=False\n)\n```"
    },
    {
      "severity": "critical",
      "category": "testing",
      "file": "tests/conftest.py",
      "line": 10,
      "description": "Test database uses SQLite instead of PostgreSQL, masking potential compatibility issues with ENUM types, JSON fields, and async behavior specific to PostgreSQL 15",
      "suggested_fix": "Use PostgreSQL test container:\n```python\nfrom testcontainers.postgres import PostgresContainer\n\n@pytest.fixture(scope=\"session\")\nasync def postgres():\n    with PostgresContainer(\"postgres:15\") as postgres:\n        yield postgres\n\n@pytest.fixture\ndef database_url(postgres):\n    return postgres.get_connection_url().replace(\"postgresql://\", \"postgresql+asyncpg://\")\n```"
    },
    {
      "severity": "high",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/messaging_conditions/routes.py",
      "line": 30,
      "description": "Bare except clause catching generic Exception violates best practices and masks unexpected errors. Custom exceptions lack status_code attribute causing AttributeError.",
      "suggested_fix": "Use specific exception handling and map to HTTPException:\n```python\nfrom mortgage_underwriting.common.exceptions import AppException, NotFoundError\n\n@router.post(\"/{application_id}/messages\")\nasync def send_message(...):\n    try:\n        service = MessagingConditionsService(db)\n        return await service.send_message(payload, current_user_id)\n    except NotFoundError as e:\n        raise HTTPException(status_code=404, detail={\"detail\": e.detail, \"error_code\": e.error_code})\n    except AppException as e:\n        raise HTTPException(status_code=400, detail={\"detail\": e.detail, \"error_code\": e.error_code})\n    except Exception as e:\n        logger.error(\"unexpected_error\", error=str(e))\n        raise HTTPException(status_code=500, detail={\"detail\": \"Internal server error\", \"error_code\": \"INTERNAL_ERROR\"})\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/messaging_conditions/services.py",
      "line": 60,
      "description": "DRY violation: Count query duplicates all filter conditions from main query in get_message_thread method, increasing maintenance burden and bug risk",
      "suggested_fix": "Extract filter building to reusable method:\n```python\ndef _apply_message_filters(query, params: MessageQueryParams):\n    if params.sender_id:\n        query = query.where(Message.sender_id == params.sender_id)\n    if params.recipient_id:\n        query = query.where(Message.recipient_id == params.recipient_id)\n    if params.date_from:\n        query = query.where(Message.sent_at >= params.date_from)\n    if params.date_to:\n        query = query.where(Message.sent_at <= params.date_to)\n    if params.is_read is not None:\n        query = query.where(Message.is_read == params.is_read)\n    return query\n\n# Use in both queries\nquery = _apply_message_filters(select(Message), params)\n```"
    },
    {
      "severity": "high",
      "category": "database",
      "file": "mortgage_underwriting/modules/messaging_conditions/services.py",
      "line": 90,
      "description": "N+1 query risk: No eager loading of relationships (sender, recipient) when fetching messages, causing additional queries when accessing user data",
      "suggested_fix": "Add selectinload for relationships:\n```python\nfrom sqlalchemy.orm import selectinload\n\nquery = select(Message).options(\n    selectinload(Message.sender),\n    selectinload(Message.recipient)\n).where(Message.application_id == application_id)\n```"
    },
    {
      "severity": "high",
      "category": "performance",
      "file": "mortgage_underwriting/modules/messaging_conditions/routes.py",
      "line": 1,
      "description": "Missing rate limiting on all endpoints exposes system to abuse and potential DoS attacks, violating security best practices",
      "suggested_fix": "Add rate limiting decorator:\n```python\nfrom slowapi import Limiter\nfrom slowapi.util import get_remote_address\n\nlimiter = Limiter(key_func=get_remote_address)\n\n@router.post(\"/{application_id}/messages\")\n@limiter.limit(\"30/minute\")\nasync def send_message(...):\n    ...\n```"
    },
    {
      "severity": "high",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/messaging_conditions/services.py",
      "line": 80,
      "description": "Missing transaction rollback on database errors: direct commit() without try/except/rollback can leave database in inconsistent state",
      "suggested_fix": "Wrap operations in try/except with rollback:\n```python\nfrom sqlalchemy.exc import SQLAlchemyError\n\nasync def send_message(self, ...):\n    try:\n        message = Message(**message_dict)\n        self.db.add(message)\n        await self.db.commit()\n        await self.db.refresh(message)\n        return message\n    except SQLAlchemyError as e:\n        await self.db.rollback()\n        logger.error(\"database_error\", error=str(e))\n        raise AppException(detail=\"Failed to send message\", error_code=\"MESSAGING_003\")\n```"
    },
    {
      "severity": "high",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/messaging_conditions/services.py",
      "line": 1,
      "description": "Service class directly commits transactions without explicit transaction context, violating unit of work pattern and making testing difficult",
      "suggested_fix": "Use dependency injection and context managers:\n```python\nfrom sqlalchemy.ext.asyncio import AsyncSession\n\nclass MessagingConditionsService:\n    def __init__(self, db: AsyncSession):\n        self.db = db\n    \n    async def send_message(self, ...):\n        async with self.db.begin():\n            message = Message(**message_dict)\n            self.db.add(message)\n            await self.db.flush()\n            await self.db.refresh(message)\n            return message\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/messaging_conditions/routes.py",
      "line": 15,
      "description": "Malformed import statement split across lines causing potential import errors and violating PEP 8",
      "suggested_fix": "Fix import statement structure:\n```python\nfrom mortgage_underwriting.modules.messaging_conditions.schemas import (\n    MessageCreate,\n    MessageUpdateRead,\n    ConditionCreate,\n    ConditionStatusUpdate,\n    MessageResponse,\n    ConditionResponse,\n    PaginatedMessageResponse,\n    PaginatedConditionResponse,\n    MessageQueryParams\n)\nfrom mortgage_underwriting.modules.messaging_conditions.services import MessagingConditionsService\n```"
    },
    {
      "severity": "medium",
      "category": "database",
      "file": "mortgage_underwriting/modules/messaging_conditions/models.py",
      "line": 8,
      "description": "Duplicate index definitions: module-level Index objects are redundant since columns already have index=True, wasting migration effort",
      "suggested_fix": "Remove redundant index declarations:\n```python\n# Delete these lines\n# message_recipient_index = Index('ix_messages_recipient_id', 'recipient_id')\n# message_application_index = Index('ix_messages_application_id', 'application_id')\n```"
    },
    {
      "severity": "medium",
      "category": "database",
      "file": "mortgage_underwriting/modules/messaging_conditions/models.py",
      "line": 35,
      "description": "ENUM types defined with create_type=False require manual database setup, increasing deployment complexity and risk of errors",
      "suggested_fix": "Use Python enum for type safety:\n```python\nfrom enum import Enum\n\nclass ConditionStatus(str, Enum):\n    OUTSTANDING = \"outstanding\"\n    SATISFIED = \"satisfied\"\n    WAIVED = \"waived\"\n\nclass ConditionType(str, Enum):\n    DOCUMENT = \"document\"\n    INFORMATION = \"information\"\n    OTHER = \"other\"\n\n# In model:\nstatus: Mapped[ConditionStatus] = mapped_column(\n    ENUM(ConditionStatus, name='condition_status_enum'),\n    default=ConditionStatus.OUTSTANDING,\n    nullable=False\n)\n```"
    },
    {
      "severity": "medium",
      "category": "performance",
      "file": "mortgage_underwriting/modules/messaging_conditions/services.py",
      "line": 95,
      "description": "Inefficient update pattern: separate SELECT after UPDATE instead of using RETURNING clause, causing extra database round-trip",
      "suggested_fix": "Use RETURNING clause:\n```python\nfrom sqlalchemy.dialects.postgresql import insert\n\nstmt = (\n    update(Message)\n    .where(...)\n    .values(is_read=True, read_at=func.now())\n    .returning(Message)\n)\nresult = await self.db.execute(stmt)\nmessage = result.scalar_one_or_none()\nif not message:\n    raise NotFoundError(...)\nreturn message\n```"
    },
    {
      "severity": "medium",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/messaging_conditions/services.py",
      "line": 20,
      "description": "Missing authorization logic: methods assume auth middleware handles access control but don't verify user belongs to application, violating security principles",
      "suggested_fix": "Add authorization checks:\n```python\nasync def send_message(self, ...):\n    # Check user is part of application\n    app_access = await self.db.execute(\n        select(MortgageApplication).where(\n            MortgageApplication.id == payload.application_id,\n            or_(\n                MortgageApplication.applicant_id == current_user_id,\n                MortgageApplication.broker_id == current_user_id\n            )\n        )\n    )\n    if not app_access.scalar_one_or_none():\n        raise UnauthorizedMessageAccessError()\n```"
    },
    {
      "severity": "medium",
      "category": "testing",
      "file": "tests/conftest.py",
      "line": 15,
      "description": "Redefinition of Base declarative class instead of importing from common.database, causing schema mismatch and test isolation issues",
      "suggested_fix": "Import from common module:\n```python\nfrom mortgage_underwriting.common.database import Base\n```"
    },
    {
      "severity": "medium",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/messaging_conditions/services.py",
      "line": 120,
      "description": "DRY violation: Count query duplication in list_conditions method similar to get_message_thread",
      "suggested_fix": "Reuse filter logic:\n```python\nquery = select(Condition).where(Condition.application_id == application_id)\ncount_query = select(func.count()).select_from(query.subquery())\n```"
    }
  ],
  "summary": "Module is BLOCKED due to critical issues: incomplete code in services.py, missing audit fields violating FINTRAC requirements, and inadequate error handling. High severity issues include DRY violations, N+1 query risks, missing rate limiting, and lack of transaction management. Medium issues involve duplicate indexes, inefficient update patterns, and missing authorization checks. All issues must be resolved before production deployment."
}
```