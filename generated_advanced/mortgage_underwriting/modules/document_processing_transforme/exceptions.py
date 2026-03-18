class DPTException(Exception):
    """Base exception for Document Processing Transformer service."""
    def __init__(self, detail: str, error_code: str) -> None:
        self.detail = detail
        self.error_code = error_code
        super().__init__(detail)