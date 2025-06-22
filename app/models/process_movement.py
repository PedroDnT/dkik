"""
Process Movement model for legal case updates.

This module defines the ProcessMovement model which stores individual movements/updates
from legal processes, including the movement details, dates, and metadata.
"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

from pydantic import Field, validator

from app.models.base import MongoBaseModel


class MovementType(str, Enum):
    """Enum for types of process movements."""
    DECISION = "decision"  # Judicial decision
    DISPATCH = "dispatch"  # Judicial dispatch
    SENTENCE = "sentence"  # Judicial sentence
    HEARING = "hearing"  # Hearing scheduled or updated
    DOCUMENT = "document"  # Document added to the process
    PETITION = "petition"  # Petition filed
    APPEAL = "appeal"  # Appeal filed or decided
    CERTIFICATION = "certification"  # Certification of events
    PUBLICATION = "publication"  # Official publication
    CONCLUSION = "conclusion"  # Conclusion to judge
    OTHER = "other"  # Other types of movements


class MovementImportance(int, Enum):
    """Enum for movement importance levels."""
    LOW = 1  # Low importance
    MEDIUM = 2  # Medium importance
    HIGH = 3  # High importance
    CRITICAL = 4  # Critical importance


class ProcessMovement(MongoBaseModel):
    """
    Process Movement model for legal case updates.
    
    Stores individual movements/updates from legal processes, including
    the movement details, dates, and metadata from the DataJud API.
    """
    # Required fields
    process_cnj: str = Field(
        ...,
        description="CNJ number of the process this movement belongs to"
    )
    movement_id: str = Field(
        ...,
        description="Unique identifier for the movement from the court system"
    )
    
    # Movement details
    date: datetime = Field(
        ...,
        description="Date and time when the movement occurred"
    )
    type: MovementType = Field(
        default=MovementType.OTHER,
        description="Type of movement"
    )
    description: str = Field(
        ...,
        description="Description of the movement"
    )
    content: Optional[str] = Field(
        None,
        description="Full content/text of the movement"
    )
    
    # Additional information
    judge: Optional[str] = Field(
        None,
        description="Judge responsible for the movement"
    )
    court_section: Optional[str] = Field(
        None,
        description="Court section where the movement occurred"
    )
    
    # Related documents
    documents: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of documents related to this movement"
    )
    
    # Importance and relevance
    importance: MovementImportance = Field(
        default=MovementImportance.MEDIUM,
        description="Importance level of the movement"
    )
    is_terminal: bool = Field(
        default=False,
        description="Whether this movement concludes the process or a phase"
    )
    
    # Notification status
    notified: bool = Field(
        default=False,
        description="Whether users have been notified about this movement"
    )
    notification_count: int = Field(
        default=0,
        description="Number of notifications sent for this movement"
    )
    last_notification_date: Optional[datetime] = Field(
        None,
        description="Date when the last notification was sent"
    )
    
    # Metadata
    datajud_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw metadata from DataJud API"
    )
    
    # Extracted entities and information
    extracted_dates: List[datetime] = Field(
        default_factory=list,
        description="Dates extracted from the movement content"
    )
    extracted_values: Dict[str, float] = Field(
        default_factory=dict,
        description="Monetary values extracted from the movement content"
    )
    extracted_entities: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Named entities extracted from the movement content"
    )
    
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
    
    @validator("documents")
    def validate_documents(cls, v):
        """Validate documents have required fields."""
        for doc in v:
            required_fields = ["id", "type", "name"]
            for field in required_fields:
                if field not in doc:
                    raise ValueError(f"Document missing required field: {field}")
        return v
    
    class Config:
        """Pydantic model configuration."""
        schema_extra = {
            "example": {
                "process_cnj": "1234567-89.2023.8.26.0000",
                "movement_id": "MOV123456",
                "date": "2023-06-10T14:30:00",
                "type": "decision",
                "description": "Decisão - Deferido o pedido de tutela antecipada",
                "content": "Vistos. Trata-se de ação de obrigação de fazer...",
                "judge": "Dr. João Silva",
                "importance": 3,
                "is_terminal": False,
                "documents": [
                    {
                        "id": "DOC123",
                        "type": "decision",
                        "name": "Decisão Interlocutória",
                        "url": "https://example.com/doc123"
                    }
                ]
            }
        }
