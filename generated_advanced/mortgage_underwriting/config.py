"""Application configuration.

Loads settings from environment variables or YAML config files.
"""

import os
from pathlib import Path
from dataclasses import dataclass

@dataclass
class DatabaseConfig:
    url: str = os.getenv("DATABASE_URL", "postgresql://dev:dev@localhost:5432/mortgage_uw")
    echo: bool = os.getenv("DB_ECHO", "true").lower() == "true"
    pool_size: int = int(os.getenv("DB_POOL_SIZE", "5"))

@dataclass
class APIConfig:
    debug: bool = os.getenv("API_DEBUG", "true").lower() == "true"
    host: str = os.getenv("API_HOST", "0.0.0.0")
    port: int = int(os.getenv("API_PORT", "8000"))
    title: str = "Mortgage Underwriting API"
    version: str = "1.0.0"

@dataclass
class SecurityConfig:
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")
    jwt_expiration: int = int(os.getenv("JWT_EXPIRATION", "86400"))
    cors_origins: list = ["*"]

class Config:
    """Application configuration."""
    database = DatabaseConfig()
    api = APIConfig()
    security = SecurityConfig()

settings = Config()
