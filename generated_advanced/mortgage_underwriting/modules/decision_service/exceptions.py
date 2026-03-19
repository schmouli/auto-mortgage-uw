class ClientException(Exception):
    """Base exception for client module"""
    pass


class ClientNotFoundError(ClientException):
    def __init__(self, client_id: int):
        self.client_id = client_id
        super().__init__(f"Client with ID {client_id} not found")


class ClientAlreadyExistsError(ClientException):
    def __init__(self, email: str):
        self.email = email
        super().__init__(f"Client with email {email} already exists")