```json
[
  {
    "title": "Docker build fails due to missing dependency installation step",
    "description": "Docker image build fails during the RUN stage where python dependencies should be installed via uv. The error indicates that pyproject.toml is not found in the context.",
    "test_name": "tests/integration/test_docker_build.py::test_dockerfile_builds_successfully",
    "error_type": "CalledProcessError",
    "stack_trace": "subprocess.CalledProcessError: Command '['docker', 'build', '-t', 'cmhc_uw_test', '.']' returned non-zero exit status 1.\n  Step 4/8 : RUN uv sync --locked\n   ---> Running in abc123\n  error: Failed to read pyproject.toml\n  Caused by: No such file or directory (os error 2)",
    "error_message": "Failed to read pyproject.toml: No such file or directory",
    "affected_code": ["Dockerfile", "line 7"],
    "suggested_fix": "Ensure WORKDIR is set correctly before COPY command so that pyproject.toml is accessible when running uv sync. Add explicit COPY ./pyproject.toml ./uv.lock* ./",
    "severity": "critical"
  },
  {
    "title": "Deployment script does not validate required environment variables",
    "description": "The deployment script attempts to start the application without checking for essential configuration like DATABASE_URL, causing runtime KeyError exceptions upon startup.",
    "test_name": "tests/integration/test_deploy_script.py::test_deploy_checks_env_vars",
    "error_type": "KeyError",
    "stack_trace": "Traceback (most recent call last):\n  File \"scripts/deploy.py\", line 15, in main\n    db_url = os.environ['DATABASE_URL']\nKeyError: 'DATABASE_URL'",
    "error_message": "'DATABASE_URL'",
    "affected_code": ["scripts/deploy.py", "line 15"],
    "suggested_fix": "Add pre-flight check using common.config.Settings() which will raise informative errors if required settings are missing",
    "severity": "high"
  },
  {
    "title": "Health check endpoint returns 500 instead of proper readiness status",
    "description": "The health check route returns HTTP 500 even when the service is running but DB connection pool is exhausted. Expected behavior is to return 200 OK with details about subsystem statuses.",
    "test_name": "tests/integration/test_health_endpoint.py::test_health_check_when_db_unreachable",
    "error_type": "AssertionError",
    "stack_trace": "def test_health_check_when_db_unreachable():\n> assert response.status_code == 200\nE AssertionError: assert 500 == 200",
    "error_message": "assert 500 == 200",
    "affected_code": ["modules/health/routes.py", "line 22"],
    "suggested_fix": "Implement graceful degradation in health checks - catch database connection issues and return {'status': 'degraded', 'database': 'unreachable'} with HTTP 200",
    "severity": "medium"
  }
]
```