"""
Process model for legal cases.

This module defines the Process model which stores information about legal cases
including CNJ number, court information, parties, status, and metadata from the DataJud API.
"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

from pydantic import Field, validator
import re

from app.models.base import MongoBaseModel


class ProcessStatus(str, Enum):
    """Enum for process status."""
    ACTIVE = "active"  # Process is active
    ARCHIVED = "archived"  # Process is archived
    CONCLUDED = "concluded"  # Process is concluded
    SUSPENDED = "suspended"  # Process is suspended
    UNKNOWN = "unknown"  # Status unknown


class ProcessType(str, Enum):
    """Enum for process type."""
    CIVIL = "civil"
    CRIMINAL = "criminal"
    LABOR = "labor"
    TAX = "tax"
    ADMINISTRATIVE = "administrative"
    ELECTORAL = "electoral"
    OTHER = "other"


class ProcessSecrecy(int, Enum):
    """Enum for process secrecy level."""
    PUBLIC = 0  # Public process
    LEVEL_1 = 1  # Basic secrecy
    LEVEL_2 = 2  # Intermediate secrecy
    LEVEL_3 = 3  # High secrecy
    LEVEL_4 = 4  # Very high secrecy
    LEVEL_5 = 5  # Maximum secrecy


class Process(MongoBaseModel):
    """
    Process model for legal cases.
    
    Stores information about legal cases including CNJ number, court information,
    parties, status, and metadata from the DataJud API.
    """
    # Required fields
    cnj_number: str = Field(
        ..., 
        description="CNJ formatted process number (NNNNNNN-DD.YYYY.J.TR.OOOO)"
    )
    
    # Basic information
    status: ProcessStatus = Field(
        default=ProcessStatus.UNKNOWN,
        description="Current status of the process"
    )
    type: ProcessType = Field(
        default=ProcessType.OTHER,
        description="Type of the process"
    )
    secrecy_level: ProcessSecrecy = Field(
        default=ProcessSecrecy.PUBLIC,
        description="Secrecy level of the process"
    )
    
    # Court information
    court: Dict[str, str] = Field(
        default_factory=dict,
        description="Court information (code, name, instance)"
    )
    jurisdiction: str = Field(
        default="",
        description="Jurisdiction of the process"
    )
    
    # Dates
    filing_date: Optional[datetime] = Field(
        None,
        description="Date when the process was filed"
    )
    distribution_date: Optional[datetime] = Field(
        None,
        description="Date when the process was distributed"
    )
    conclusion_date: Optional[datetime] = Field(
        None,
        description="Date when the process was concluded (if applicable)"
    )
    
    # Parties
    parties: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of parties involved in the process (plaintiff, defendant, etc.)"
    )
    
    # Process details
    subject: str = Field(
        default="",
        description="Subject of the process"
    )
    value: float = Field(
        default=0.0,
        description="Value of the process in BRL"
    )
    
    # Assigned judge/court
    assigned_to: Dict[str, str] = Field(
        default_factory=dict,
        description="Judge or court assigned to the process"
    )
    
    # Hearings
    hearings: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of scheduled hearings"
    )
    
    # Movements
    last_movement_date: Optional[datetime] = Field(
        None,
        description="Date of the last movement"
    )
    last_movement_description: str = Field(
        default="",
        description="Description of the last movement"
    )
    last_movement_id: str = Field(
        default="",
        description="ID of the last movement"
    )
    
    # Metadata
    datajud_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw metadata from DataJud API"
    )
    
    # Tracking
    last_checked: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the process was last checked for updates"
    )
    is_tracked: bool = Field(
        default=False,
        description="Whether the process is being tracked by any user"
    )
    tracking_count: int = Field(
        default=0,
        description="Number of users tracking this process"
    )
    
    @validator("cnj_number")
    def validate_cnj_number(cls, v):
        """Validate CNJ number format."""
        # CNJ format: NNNNNNN-DD.YYYY.J.TR.OOOO
        pattern = r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$"
        if not re.match(pattern, v):
            raise ValueError(
                "Invalid CNJ number format. Expected: NNNNNNN-DD.YYYY.J.TR.OOOO"
            )
        return v
    
    @validator("hearings")
    def validate_hearings(cls, v):
        """Validate hearings have required fields."""
        for hearing in v:
            required_fields = ["date", "type", "location"]
            for field in required_fields:
                if field not in hearing:
                    raise ValueError(f"Hearing missing required field: {field}")
        return v
    
    @validator("parties")
    def validate_parties(cls, v):
        """Validate parties have required fields."""
        for party in v:
            required_fields = ["role", "name"]
            for field in required_fields:
                if field not in party:
                    raise ValueError(f"Party missing required field: {field}")
        return v
    
    class Config:
        """Pydantic model configuration."""
        schema_extra = {
            "example": {
                "cnj_number": "1234567-89.2023.8.26.0000",
                "status": "active",
                "type": "civil",
                "secrecy_level": 0,
                "court": {
                    "code": "TJSP",
                    "name": "Tribunal de Justiça de São Paulo",
                    "instance": "1"
                },
                "jurisdiction": "São Paulo - Capital",
                "filing_date": "2023-01-15T00:00:00",
                "parties": [
                    {
                        "role": "plaintiff",
                        "name": "João Silva",
                        "document": "123.456.789-00"
                    },
                    {
                        "role": "defendant",
                        "name": "Empresa XYZ Ltda",
                        "document": "12.345.678/0001-90"
                    }
                ],
                "subject": "Ação de Indenização por Danos Morais",
                "value": 50000.00,
                "last_movement_date": "2023-06-10T14:30:00",
                "last_movement_description": "Conclusos para Despacho",
                "last_movement_id": "MOV123456"
            }
        }
