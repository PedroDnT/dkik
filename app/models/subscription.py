"""
Subscription model for linking users to processes they track.

This module defines the Subscription model which connects users to legal processes
they are tracking, including tracking preferences and notification settings.
"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set

from pydantic import Field, validator

from app.models.base import MongoBaseModel


class TrackingType(str, Enum):
    """Enum for types of process updates to track."""
    ALL = "all"  # Track all updates
    MOVEMENTS = "movements"  # Track only new movements
    HEARINGS = "hearings"  # Track only hearing updates
    DECISIONS = "decisions"  # Track only decisions
    CONCLUSIONS = "conclusions"  # Track only conclusions


class NotificationFrequency(str, Enum):
    """Enum for notification frequency."""
    IMMEDIATE = "immediate"  # Send notifications immediately
    DAILY = "daily"  # Send a daily digest
    WEEKLY = "weekly"  # Send a weekly digest


class Subscription(MongoBaseModel):
    """
    Subscription model for linking users to processes they track.
    
    Connects users to legal processes they are tracking and stores
    tracking preferences and notification settings.
    """
    # Required fields - references to User and Process
    user_id: str = Field(..., description="ID of the user tracking the process")
    process_cnj: str = Field(..., description="CNJ number of the tracked process")
    
    # Tracking preferences
    tracking_types: List[TrackingType] = Field(
        default=[TrackingType.ALL],
        description="Types of updates to track"
    )
    
    # Notification settings
    notification_frequency: NotificationFrequency = Field(
        default=NotificationFrequency.IMMEDIATE,
        description="Frequency of notifications"
    )
    notification_channels: List[str] = Field(
        default=["whatsapp"],
        description="Channels to send notifications through"
    )
    
    # Custom labels and notes
    label: Optional[str] = Field(
        None,
        description="User-defined label for this subscription"
    )
    notes: Optional[str] = Field(
        None,
        description="User-defined notes about this subscription"
    )
    
    # Tracking metadata
    is_active: bool = Field(
        default=True,
        description="Whether this subscription is active"
    )
    last_notification_sent: Optional[datetime] = Field(
        None,
        description="When the last notification was sent"
    )
    last_movement_notified: Optional[str] = Field(
        None,
        description="ID of the last movement that triggered a notification"
    )
    notifications_sent_today: int = Field(
        default=0,
        description="Number of notifications sent today"
    )
    notifications_sent_total: int = Field(
        default=0,
        description="Total number of notifications sent for this subscription"
    )
    
    # Custom filters
    movement_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords to filter movements by (notify only if movement contains these keywords)"
    )
    exclude_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords to exclude movements by (don't notify if movement contains these keywords)"
    )
    
    # Importance and priority
    importance: int = Field(
        default=1,
        description="User-defined importance (1-5, with 5 being highest)"
    )
    
    # Expiration
    expires_at: Optional[datetime] = Field(
        None,
        description="When this subscription expires (if applicable)"
    )
    
    @validator("importance")
    def validate_importance(cls, v):
        """Validate importance is between 1 and 5."""
        if not 1 <= v <= 5:
            raise ValueError("Importance must be between 1 and 5")
        return v
    
    @validator("notifications_sent_today")
    def validate_notifications_sent_today(cls, v):
        """Validate notifications_sent_today is non-negative."""
        if v < 0:
            raise ValueError("notifications_sent_today cannot be negative")
        return v
    
    @validator("process_cnj")
    def validate_process_cnj(cls, v):
        """Validate CNJ number format."""
        import re
        pattern = r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$"
        if not re.match(pattern, v):
            raise ValueError(
                "Invalid CNJ number format. Expected: NNNNNNN-DD.YYYY.J.TR.OOOO"
            )
        return v
    
    class Config:
        """Pydantic model configuration."""
        schema_extra = {
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "process_cnj": "1234567-89.2023.8.26.0000",
                "tracking_types": ["movements", "hearings"],
                "notification_frequency": "immediate",
                "notification_channels": ["whatsapp"],
                "label": "Client XYZ - Contract Dispute",
                "is_active": True,
                "importance": 3,
                "movement_keywords": ["sentença", "decisão", "despacho"],
                "exclude_keywords": ["vista", "juntada"]
            }
        }
