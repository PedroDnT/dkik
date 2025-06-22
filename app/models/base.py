"""
Base model for MongoDB documents.

This module provides a base model class that all MongoDB document models will inherit from,
providing common fields and functionality such as ID and timestamp handling.
"""
from datetime import datetime
from typing import Any, Dict, Optional

from bson import ObjectId
from pydantic import BaseModel, Field, validator


class PyObjectId(ObjectId):
    """Custom ObjectId type for proper serialization/deserialization."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
    
    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


class MongoBaseModel(BaseModel):
    """
    Base model for all MongoDB documents.
    
    Provides common fields and functionality for MongoDB documents:
    - id: MongoDB ObjectId as string
    - created_at: Timestamp when document was created
    - updated_at: Timestamp when document was last updated
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator("updated_at", always=True)
    def set_updated_at(cls, v, values):
        """Always update the updated_at field when the model is validated."""
        return datetime.utcnow()
    
    def dict(self, **kwargs) -> Dict[str, Any]:
        """Override dict method to convert ObjectId to string."""
        dict_repr = super().dict(**kwargs)
        
        # Convert ObjectId to string for JSON serialization
        if "_id" in dict_repr and dict_repr["_id"]:
            dict_repr["_id"] = str(dict_repr["_id"])
        
        return dict_repr
    
    class Config:
        """Pydantic model configuration."""
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat(),
        }
        schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
            }
        }
