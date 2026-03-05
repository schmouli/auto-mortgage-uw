class JobExecutionError(Exception):
    """Raised when a background job execution fails"""
    pass


class JobNotFoundError(Exception):
    """Raised when a requested job cannot be found"""
    pass
```