"""
Configuration settings for the Horoz Demir MRP System.
Manages environment variables, database settings, and application configuration.
"""

from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import validator
import os


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Database Configuration  
    DATABASE_URL: str = "sqlite:///./test_mrp.db"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    
    # Security Settings
    SECRET_KEY: str = "horoz_demir_mrp_secret_key_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS Configuration
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://localhost:3000",
        "http://192.168.1.172:3000",
        "https://192.168.1.172:3000"
    ]
    
    # Allow local network access in development
    ALLOW_LOCAL_NETWORK: bool = True
    LOCAL_NETWORK_RANGES: List[str] = ["192.168.1.", "10.0.0.", "172.16."]
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # Application Settings
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Horoz Demir MRP System"
    PROJECT_DESCRIPTION: str = "Material Requirements Planning System for Manufacturing"
    VERSION: str = "1.0.0"
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 100
    
    # Redis Configuration (for caching and session management)
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    REDIS_EXPIRE_SECONDS: int = 3600
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None
    
    # File Upload Settings
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    UPLOAD_DIR: str = "uploads"
    ALLOWED_FILE_EXTENSIONS: List[str] = [".xlsx", ".xls", ".csv", ".pdf"]
    
    # Report Generation Settings
    REPORT_CACHE_EXPIRE: int = 300  # 5 minutes
    MAX_REPORT_RECORDS: int = 10000
    
    # Business Logic Settings
    DEFAULT_CURRENCY: str = "TRY"
    DEFAULT_TIMEZONE: str = "Europe/Istanbul"
    FIFO_BATCH_SIZE: int = 100
    
    @validator('DATABASE_URL', pre=True)
    def validate_database_url(cls, v):
        """Validate database URL format."""
        if not v or not v.startswith(('postgresql://', 'postgresql+asyncpg://', 'sqlite:///')):
            raise ValueError('DATABASE_URL must be a valid PostgreSQL or SQLite URL')
        return v
    
    @validator('SECRET_KEY', pre=True)
    def validate_secret_key(cls, v):
        """Validate secret key strength."""
        if not v or len(v) < 32:
            raise ValueError('SECRET_KEY must be at least 32 characters long')
        return v
    
    @validator('ALLOWED_ORIGINS', pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = True


# Create global settings instance
settings = Settings()


# Environment-specific configurations
class DevelopmentConfig(Settings):
    """Development environment configuration."""
    DEBUG: bool = True
    DB_ECHO: bool = True
    LOG_LEVEL: str = "DEBUG"
    ALLOW_LOCAL_NETWORK: bool = True


class ProductionConfig(Settings):
    """Production environment configuration."""
    DEBUG: bool = False
    DB_ECHO: bool = False
    LOG_LEVEL: str = "WARNING"
    ALLOW_LOCAL_NETWORK: bool = False
    ALLOWED_HOSTS: List[str] = ["your-domain.com", "www.your-domain.com"]


class TestingConfig(Settings):
    """Testing environment configuration."""
    DEBUG: bool = True
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/horoz_demir_mrp_test"
    REDIS_URL: Optional[str] = "redis://localhost:6379/1"


def get_settings() -> Settings:
    """Get configuration based on environment."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    if env == "production":
        return ProductionConfig()
    elif env == "testing":
        return TestingConfig()
    else:
        return DevelopmentConfig()


# Use environment-specific settings
settings = get_settings()