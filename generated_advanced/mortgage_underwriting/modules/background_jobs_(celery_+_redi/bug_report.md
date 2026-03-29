```json
[
  {
    "title": "Background job retry logic fails with Redis timeout",
    "description": "Background task retries exceed limit due to Redis connection timeout during high load. Job state not persisted correctly.",
    "test_name": "tests/unit/test_background_jobs.py::test_job_retry_exceed_limit",
    "error_type": "TimeoutError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/opt/project/mortgage_underwriting/modules/background_jobs/services.py\", line 78, in execute_job\n    result = await self._run_task(task)\n  File \"/opt/project/mortgage_underwriting/modules/background_jobs/services.py\", line 102, in _run_task\n    await redis_client.setex(f\"job:{task.id}\", 60, json.dumps(result))\n  File \"/opt/project/.venv/lib/python3.12/site-packages/redis/asyncio/client.py\", line 452, in setex\n    return await self.execute_command('SETEX', name, time, value)\n  File \"/opt/project/.venv/lib/python3.12/site-packages/redis/asyncio/client.py\", line 521, in execute_command\n    conn = await self.connection_pool.get_connection(command_name, **options)\n  File \"/opt/project/.venv/lib/python3.12/site-packages/redis/asyncio/connection.py\", line 1134, in get_connection\n    await connection.connect()\n  File \"/opt/project/.venv/lib/python3.12/site-packages/redis/asyncio/connection.py\", line 309, in connect\n    raise TimeoutError(\"Connection timed out\")\nredis.exceptions.TimeoutError: Connection timed out",
    "error_message": "Connection timed out",
    "affected_code": [
      "modules/background_jobs/services.py",
      "line 102"
    ],
    "suggested_fix": "Implement exponential backoff and circuit breaker pattern for Redis operations; add retry count tracking in DB instead of relying solely on Redis state.",
    "severity": "high"
  },
  {
    "title": "Job serialization fails for complex DTO objects",
    "description": "Celery job arguments containing nested Pydantic models fail during serialization due to lack of custom encoder support.",
    "test_name": "tests/unit/test_background_jobs.py::test_serialize_complex_dto",
    "error_type": "TypeError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/opt/project/mortgage_underwriting/modules/background_jobs/routes.py\", line 34, in queue_background_job\n    job = await background_service.enqueue(job_request)\n  File \"/opt/project/mortgage_underwriting/modules/background_jobs/services.py\", line 56, in enqueue\n    task = self.celery_app.send_task('process_underwriting', args=[dto.model_dump()])\n  File \"/opt/project/.venv/lib/python3.12/site-packages/celery/app/base.py\", line 768, in send_task\n    message = self.amqp.create_task_message(\n  File \"/opt/project/.venv/lib/python3.12/site-packages/celery/app/amqp.py\", line 381, in create_task_message\n    body = self.prepare_args(args)\n  File \"/opt/project/.venv/lib/python3.12/site-packages/celery/app/amqp.py\", line 296, in prepare_args\n    return dumps(args, serializer=self.serializer)\n  File \"/opt/project/.venv/lib/python3.12/site-packages/kombu/utils/json.py\", line 68, in dumps\n    return _dumps(o, default=default)\n  File \"/usr/local/lib/python3.12/json/__init__.py\", line 238, in dumps\n    **kw).encode(obj)\n  File \"/usr/local/lib/python3.12/json/encoder.py\", line 200, in encode\n    chunks = self.iterencode(o, _one_shot=True)\n  File \"/usr/local/lib/python3.12/json/encoder.py\", line 258, in iterencode\n    return _iterencode(o, 0)\n  File \"/opt/project/.venv/lib/python3.12/site-packages/kombu/utils/json.py\", line 58, in dumper\n    return default(o)\n  File \"/opt/project/.venv/lib/python3.12/site-packages/pydantic/main.py\", line 421, in pydantic_encoder\n    return dict(obj)\nTypeError: cannot convert dictionary update sequence element #0 to a sequence",
    "error_message": "cannot convert dictionary update sequence element #0 to a sequence",
    "affected_code": [
      "modules/background_jobs/services.py",
      "line 56"
    ],
    "suggested_fix": "Register Pydantic's jsonable_encoder as the Celery task serializer or ensure all DTOs passed to background jobs are fully serializable via model_dump(mode='json').",
    "severity": "high"
  },
  {
    "title": "Missing index on job status column causes slow query",
    "description": "Querying background jobs by status takes over 2 seconds due to missing database index on 'status' field in JobModel.",
    "test_name": "tests/integration/test_background_jobs_integration.py::test_filter_jobs_by_status_slow_query",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/opt/project/tests/integration/test_background_jobs_integration.py\", line 67, in test_filter_jobs_by_status_slow_query\n    assert duration < timedelta(seconds=1), f\"Query took {duration}, expected less than 1 second\"\nAssertionError: Query took 0:00:02.134212, expected less than 1 second",
    "error_message": "Query took 0:00:02.134212, expected less than 1 second",
    "affected_code": [
      "modules/background_jobs/models.py",
      "line 23"
    ],
    "suggested_fix": "Add composite index on (status, created_at) in JobModel to optimize filtering and sorting queries.",
    "severity": "medium"
  },
  {
    "title": "Job cleanup routine deletes active tasks prematurely",
    "description": "The cleanup_expired_jobs service method deletes jobs younger than retention period including those still processing, violating FINTRAC immutability rules.",
    "test_name": "tests/unit/test_background_jobs.py::test_cleanup_does_not_delete_active_jobs",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/opt/project/tests/unit/test_background_jobs.py\", line 98, in test_cleanup_does_not_delete_active_jobs\n    assert job.status == JobStatus.PROCESSING\nAssertionError: assert <JobStatus.FAILED: 'failed'> == <JobStatus.PROCESSING: 'processing'>",
    "error_message": "assert <JobStatus.FAILED: 'failed'> == <JobStatus.PROCESSING: 'processing'>",
    "affected_code": [
      "modules/background_jobs/services.py",
      "line 142"
    ],
    "suggested_fix": "Update cleanup_expired_jobs to exclude jobs with status in [PROCESSING, QUEUED] regardless of age. Add unit test covering this edge case.",
    "severity": "high"
  }
]
```