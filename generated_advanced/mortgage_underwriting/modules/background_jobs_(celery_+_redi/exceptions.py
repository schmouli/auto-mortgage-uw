from mortgage_underwriting.common.exceptions import AppException


class ScheduledJobsError(AppException):
    """Base exception for scheduled jobs module."""
    pass


class JobExecutionNotFoundError(ScheduledJobsError):
    """Raised when a job execution cannot be found."""
    def __init__(self, job_id: str) -> None:  # FIXED: Added return type hint
        self.job_id = job_id
        super().__init__(f"Job execution {job_id} not found")