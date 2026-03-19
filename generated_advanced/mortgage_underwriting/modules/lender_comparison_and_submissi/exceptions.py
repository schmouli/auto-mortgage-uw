class LenderNotFoundError(Exception):
    """Raised when a requested lender is not found."""
    def __init__(self, lender_id: int):
        self.lender_id = lender_id
        super().__init__(f"Lender with ID {lender_id} not found")


class ProductNotFoundError(Exception):
    """Raised when a requested product is not found."""
    def __init__(self, product_id: int):
        self.product_id = product_id
        super().__init__(f"Product with ID {product_id} not found")


class SubmissionNotFoundError(Exception):
    """Raised when a requested submission is not found."""
    def __init__(self, submission_id: int):
        self.submission_id = submission_id
        super().__init__(f"Submission with ID {submission_id} not found")