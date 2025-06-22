"""
User model for WhatsApp bot users.

This module defines the User model which stores information about WhatsApp users
including phone number, subscription status, preferences, and tracking metadata.
"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import Field, validator

from app.models.base import MongoBaseModel


class SubscriptionStatus(str, Enum):
    """Enum for user subscription status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRIAL = "trial"
    EXPIRED = "expired"


class SubscriptionTier(str, Enum):
    """Enum for user subscription tier."""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"


class Language(str, Enum):
    """Enum for user language preference."""
    PT_BR = "pt-BR"  # Portuguese (Brazil)
    EN_US = "en-US"  # English (US)


class NotificationPreference(str, Enum):
    """Enum for notification preferences."""
    ALL = "all"  # Receive all notifications
    IMPORTANT = "important"  # Only important notifications
    NONE = "none"  # No notifications


class User(MongoBaseModel):
    """
    User model for WhatsApp bot users.
    
    Stores information about WhatsApp users including phone number,
    subscription status, preferences, and tracking metadata.
    """
    # Required fields
    phone_number: str = Field(..., description="User's WhatsApp phone number")
    
    # Basic information
    name: Optional[str] = Field(None, description="User's name")
    email: Optional[str] = Field(None, description="User's email address")
    
    # Subscription information
    subscription_status: SubscriptionStatus = Field(
        default=SubscriptionStatus.TRIAL,
        description="User's subscription status"
    )
    subscription_tier: SubscriptionTier = Field(
        default=SubscriptionTier.FREE,
        description="User's subscription tier"
    )
    subscription_expires_at: Optional[datetime] = Field(
        None, 
        description="When the user's subscription expires"
    )
    
    # Preferences
    language: Language = Field(
        default=Language.PT_BR,
        description="User's preferred language"
    )
    notification_preference: NotificationPreference = Field(
        default=NotificationPreference.ALL,
        description="User's notification preferences"
    )
    notification_hours: Dict[str, int] = Field(
        default={"start": 8, "end": 20},
        description="Hours during which notifications can be sent (24-hour format)"
    )
    
    # Tracking metadata
    last_active: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the user was last active"
    )
    total_queries: int = Field(
        default=0,
        description="Total number of queries made by the user"
    )
    total_cases_tracked: int = Field(
        default=0,
        description="Total number of cases tracked by the user"
    )
    is_verified: bool = Field(
        default=False,
        description="Whether the user has been verified as a lawyer"
    )
    oab_number: Optional[str] = Field(
        None,
        description="User's OAB (Ordem dos Advogados do Brasil) registration number"
    )
    
    # Usage limits
    max_cases: int = Field(
        default=5,
        description="Maximum number of cases the user can track"
    )
    max_notifications_per_day: int = Field(
        default=10,
        description="Maximum number of notifications the user can receive per day"
    )
    
    # Device information
    device_info: Dict = Field(
        default_factory=dict,
        description="Information about the user's device"
    )
    
    # Whitelist status
    is_whitelisted: bool = Field(
        default=False,
        description="Whether the user is on the whitelist"
    )
    
    @validator("phone_number")
    def validate_phone_number(cls, v):
        """Validate phone number format."""
        # Basic validation - should start with + and contain only digits
        if not v.startswith("+") or not v[1:].isdigit():
            raise ValueError("Phone number must be in international format (e.g., +5511999998888)")
        return v
    
    @validator("notification_hours")
    def validate_notification_hours(cls, v):
        """Validate notification hours."""
        if "start" not in v or "end" not in v:
            raise ValueError("Notification hours must include 'start' and 'end' keys")
        
        start = v["start"]
        end = v["end"]
        
        if not isinstance(start, int) or not isinstance(end, int):
            raise ValueError("Notification hours must be integers")
        
        if not 0 <= start <= 23 or not 0 <= end <= 23:
            raise ValueError("Notification hours must be between 0 and 23")
        
        return v
    
    class Config:
        """Pydantic model configuration."""
        schema_extra = {
            "example": {
                "phone_number": "+5511999998888",
                "name": "João Silva",
                "email": "joao.silva@example.com",
                "subscription_status": "active",
                "subscription_tier": "basic",
                "language": "pt-BR",
                "notification_preference": "all",
                "notification_hours": {"start": 8, "end": 20},
                "is_verified": True,
                "oab_number": "123456/SP"
            }
        }
