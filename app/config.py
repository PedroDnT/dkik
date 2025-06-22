"""
Configuration module for the DKIK WhatsApp Bot.

This module uses Pydantic's BaseSettings to load and validate environment variables
with proper typing and validation for all project settings.
"""
from typing import List, Optional, Set
from pydantic import BaseSettings, Field, validator, AnyHttpUrl
from pydantic.networks import PostgresDsn, MongoUrl
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
env_path = Path(".") / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables with type validation.
    """
    # Project Info
    PROJECT_NAME: str = "DKIK - WhatsApp Bot for São Paulo State Lawyers"
    PROJECT_VERSION: str = "0.1.0"
    PROJECT_DESCRIPTION: str = "WhatsApp bot for tracking TJSP case statuses and notifications"
    
    # API Settings
    API_PREFIX: str = "/api"
    DEBUG: bool = Field(False, env="DEBUG")
    
    # FastAPI Configuration
    HOST: str = Field("0.0.0.0", env="HOST")
    PORT: int = Field(8000, env="PORT")
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    
    # Twilio WhatsApp Configuration
    TWILIO_ACCOUNT_SID: str = Field(..., env="TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: str = Field(..., env="TWILIO_AUTH_TOKEN")
    TWILIO_WHATSAPP_NUMBER: str = Field(..., env="TWILIO_WHATSAPP_NUMBER")
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    OPENAI_MODEL: str = Field("gpt-4-turbo-preview", env="OPENAI_MODEL")
    
    # DataJud API Configuration
    DATAJUD_API_KEY: str = Field(..., env="DATAJUD_API_KEY")
    DATAJUD_API_BASE_URL: str = Field(
        "https://api.datajud.cnj.jus.br/v1", 
        env="DATAJUD_API_BASE_URL"
    )
    
    # MongoDB Configuration
    MONGODB_URI: str = Field(..., env="MONGODB_URI")
    MONGODB_DB_NAME: str = Field("dkik", env="MONGODB_DB_NAME")
    
    # Background Worker Configuration
    WORKER_POLLING_INTERVAL_MINUTES: int = Field(15, env="WORKER_POLLING_INTERVAL_MINUTES")
    WORKER_MAX_CONCURRENT_TASKS: int = Field(10, env="WORKER_MAX_CONCURRENT_TASKS")
    
    # Security Configuration
    ALLOWED_PHONE_NUMBERS: List[str] = Field([], env="ALLOWED_PHONE_NUMBERS")
    JWT_SECRET: str = Field(..., env="JWT_SECRET")
    JWT_ALGORITHM: str = Field("HS256", env="JWT_ALGORITHM")
    JWT_EXPIRATION_DAYS: int = Field(30, env="JWT_EXPIRATION_DAYS")
    
    # Notification Settings
    MAX_NOTIFICATIONS_PER_DAY: int = Field(10, env="MAX_NOTIFICATIONS_PER_DAY")
    NOTIFICATION_START_HOUR: int = Field(8, env="NOTIFICATION_START_HOUR")
    NOTIFICATION_END_HOUR: int = Field(20, env="NOTIFICATION_END_HOUR")
    
    @validator("ALLOWED_PHONE_NUMBERS", pre=True)
    def parse_allowed_phone_numbers(cls, v):
        """Parse comma-separated list of phone numbers into a Python list."""
        if isinstance(v, str) and v:
            return [phone.strip() for phone in v.split(",")]
        return v
    
    @validator("NOTIFICATION_START_HOUR", "NOTIFICATION_END_HOUR")
    def validate_hour_range(cls, v):
        """Validate that hour values are between 0 and 23."""
        if not 0 <= v <= 23:
            raise ValueError(f"Hour must be between 0 and 23, got {v}")
        return v
    
    @validator("WORKER_POLLING_INTERVAL_MINUTES")
    def validate_polling_interval(cls, v):
        """Validate that polling interval is at least 5 minutes."""
        if v < 5:
            raise ValueError(f"Polling interval must be at least 5 minutes, got {v}")
        return v
    
    class Config:
        """Pydantic configuration class."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Create global settings instance
settings = Settings()
