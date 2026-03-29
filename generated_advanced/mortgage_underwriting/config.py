"""Application configuration.

Loads settings from environment variables or YAML config files.
"""

import logging
import os
import warnings
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    url: str = os.getenv("DATABASE_URL", "postgresql://dev:dev@localhost:5432/mortgage_uw")
    echo: bool = os.getenv("DB_ECHO", "false").lower() == "true"
    pool_size: int = int(os.getenv("DB_POOL_SIZE", "5"))

@dataclass
class APIConfig:
    debug: bool = os.getenv("API_DEBUG", "false").lower() == "true"
    host: str = os.getenv("API_HOST", "0.0.0.0")
    port: int = int(os.getenv("API_PORT", "8000"))
    title: str = "Mortgage Underwriting API"
    version: str = "1.0.0"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

@dataclass
class SecurityConfig:
    secret_key: str = os.getenv("SECRET_KEY", "")
    jwt_expiration: int = int(os.getenv("JWT_EXPIRATION", "86400"))
    cors_origins: list = field(default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(","))

    def __post_init__(self):
        """Validate security configuration."""
        if not self.secret_key:
            msg = (
                "SECRET_KEY environment variable not set. Generating ephemeral key for development. "
                "WARNING: All tokens will be invalidated on restart or in multi-worker deployments."
            )
            logger.warning(msg)
            warnings.warn(msg, RuntimeWarning)
            self.secret_key = os.urandom(32).hex()
        elif len(self.secret_key) < 32:
            msg = (
                f"SECRET_KEY is too short ({len(self.secret_key)} chars). "
                "Minimum 32 characters recommended for production security."
            )
            logger.warning(msg)
            warnings.warn(msg, RuntimeWarning)
        if self.cors_origins == [""]:
            self.cors_origins = ["http://localhost:3000", "http://localhost:8000"]

class Config:
    """Application configuration."""
    database = DatabaseConfig()
    api = APIConfig()
    security = SecurityConfig()

settings = Config()
