"""
Notification model for tracking messages sent to users.

This module defines the Notification model which stores information about all notifications
sent to users, including delivery status, message content, and metadata for analytics.
"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

from pydantic import Field, validator

from app.models.base import MongoBaseModel


class NotificationType(str, Enum):
    """Enum for types of notifications."""
    MOVEMENT = "movement"  # Notification about a new process movement
    HEARING = "hearing"  # Notification about a hearing (reminder or update)
    DEADLINE = "deadline"  # Notification about an approaching deadline
    SUBSCRIPTION = "subscription"  # Notification about subscription status
    WELCOME = "welcome"  # Welcome message for new users
    SYSTEM = "system"  # System notification (maintenance, updates)
    CUSTOM = "custom"  # Custom message sent by admin


class DeliveryStatus(str, Enum):
    """Enum for message delivery status."""
    QUEUED = "queued"  # Message is queued for delivery
    SENT = "sent"  # Message has been sent to Twilio
    DELIVERED = "delivered"  # Message has been delivered to the user's device
    READ = "read"  # Message has been read by the user
    FAILED = "failed"  # Message delivery failed


class NotificationPriority(int, Enum):
    """Enum for notification priority levels."""
    LOW = 1  # Low priority notification
    NORMAL = 2  # Normal priority notification
    HIGH = 3  # High priority notification
    URGENT = 4  # Urgent notification


class Notification(MongoBaseModel):
    """
    Notification model for tracking messages sent to users.
    
    Stores information about all notifications sent to users, including
    delivery status, message content, and metadata for analytics.
    """
    # Required fields - references to User and Process
    user_id: str = Field(..., description="ID of the user receiving the notification")
    phone_number: str = Field(..., description="WhatsApp phone number of the recipient")
    
    # Optional reference to process and movement
    process_cnj: Optional[str] = Field(
        None,
        description="CNJ number of the related process (if applicable)"
    )
    movement_id: Optional[str] = Field(
        None,
        description="ID of the related movement (if applicable)"
    )
    subscription_id: Optional[str] = Field(
        None,
        description="ID of the related subscription (if applicable)"
    )
    
    # Notification content
    type: NotificationType = Field(
        ...,
        description="Type of notification"
    )
    title: str = Field(
        ...,
        description="Short title or subject of the notification"
    )
    message: str = Field(
        ...,
        description="Full message content of the notification"
    )
    template_id: Optional[str] = Field(
        None,
        description="ID of the Twilio template used (if applicable)"
    )
    template_params: Dict[str, str] = Field(
        default_factory=dict,
        description="Parameters used with the template"
    )
    
    # Media content
    media_urls: List[str] = Field(
        default_factory=list,
        description="URLs of media files attached to the notification"
    )
    
    # Delivery information
    delivery_status: DeliveryStatus = Field(
        default=DeliveryStatus.QUEUED,
        description="Current delivery status of the notification"
    )
    priority: NotificationPriority = Field(
        default=NotificationPriority.NORMAL,
        description="Priority level of the notification"
    )
    channel: str = Field(
        default="whatsapp",
        description="Channel used to send the notification"
    )
    
    # Timestamps
    scheduled_for: Optional[datetime] = Field(
        None,
        description="When the notification is scheduled to be sent (if scheduled)"
    )
    sent_at: Optional[datetime] = Field(
        None,
        description="When the notification was sent"
    )
    delivered_at: Optional[datetime] = Field(
        None,
        description="When the notification was delivered"
    )
    read_at: Optional[datetime] = Field(
        None,
        description="When the notification was read"
    )
    
    # Delivery attempts and tracking
    delivery_attempts: int = Field(
        default=0,
        description="Number of delivery attempts"
    )
    max_delivery_attempts: int = Field(
        default=3,
        description="Maximum number of delivery attempts"
    )
    last_attempt_at: Optional[datetime] = Field(
        None,
        description="When the last delivery attempt was made"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if delivery failed"
    )
    
    # External service IDs
    twilio_sid: Optional[str] = Field(
        None,
        description="Twilio message SID for tracking"
    )
    
    # User interaction
    user_response: Optional[str] = Field(
        None,
        description="User's response to the notification (if any)"
    )
    response_received_at: Optional[datetime] = Field(
        None,
        description="When the user's response was received"
    )
    
    # Analytics data
    notification_group_id: Optional[str] = Field(
        None,
        description="ID grouping related notifications (e.g., for campaigns)"
    )
    analytics_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional data for analytics"
    )
    
    @validator("process_cnj")
    def validate_process_cnj(cls, v):
        """Validate CNJ number format if provided."""
        if v is not None:
            import re
            pattern = r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$"
            if not re.match(pattern, v):
                raise ValueError(
                    "Invalid CNJ number format. Expected: NNNNNNN-DD.YYYY.J.TR.OOOO"
                )
        return v
    
    @validator("phone_number")
    def validate_phone_number(cls, v):
        """Validate phone number format."""
        # Basic validation - should start with + and contain only digits
        if not v.startswith("+") or not v[1:].isdigit():
            raise ValueError("Phone number must be in international format (e.g., +5511999998888)")
        return v
    
    @validator("delivery_attempts")
    def validate_delivery_attempts(cls, v):
        """Validate delivery_attempts is non-negative."""
        if v < 0:
            raise ValueError("delivery_attempts cannot be negative")
        return v
    
    @validator("media_urls")
    def validate_media_urls(cls, v):
        """Validate media URLs."""
        for url in v:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Invalid media URL: {url}")
        return v
    
    class Config:
        """Pydantic model configuration."""
        schema_extra = {
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "phone_number": "+5511999998888",
                "process_cnj": "1234567-89.2023.8.26.0000",
                "movement_id": "MOV123456",
                "type": "movement",
                "title": "Nova Movimentação",
                "message": "Processo 1234567-89.2023.8.26.0000 teve nova movimentação: Decisão - Deferido o pedido de tutela antecipada",
                "delivery_status": "delivered",
                "priority": 2,
                "sent_at": "2023-06-10T15:30:00",
                "delivered_at": "2023-06-10T15:30:05",
                "twilio_sid": "SM123456789abcdef",
                "analytics_data": {
                    "campaign_id": "movement_updates",
                    "user_segment": "active_premium"
                }
            }
        }
