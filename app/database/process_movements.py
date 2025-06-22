"""
Process Movement database operations for the DKIK WhatsApp Bot.

This module provides a ProcessMovementDB class that extends BaseDB to handle
process movement-specific database operations such as finding movements by process CNJ,
filtering by date ranges, and managing notification status.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from bson import ObjectId
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.database.base import BaseDB, DatabaseError, DocumentNotFoundError, DuplicateDocumentError
from app.models.process_movement import ProcessMovement, MovementType, MovementImportance

# Configure logger
logger = logging.getLogger(__name__)


class ProcessMovementDB(BaseDB[ProcessMovement, ProcessMovement, ProcessMovement]):
    """
    Process Movement database operations class.
    
    This class extends BaseDB to provide process movement-specific database operations
    such as finding movements by process CNJ, filtering by date ranges,
    and managing notification status.
    """
    
    async def get_by_process_cnj(
        self,
        process_cnj: str,
        limit: int = 10,
        skip: int = 0,
        sort_direction: int = -1  # -1 for descending (newest first)
    ) -> List[ProcessMovement]:
        """
        Get movements for a specific process.
        
        Args:
            process_cnj: CNJ formatted process number
            limit: Maximum number of movements to return
            skip: Number of movements to skip (for pagination)
            sort_direction: Sort direction (1 for ascending, -1 for descending)
            
        Returns:
            List of process movement objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={"process_cnj": process_cnj},
            sort=[("date", sort_direction)],
            skip=skip,
            limit=limit
        )
    
    async def get_by_movement_id(
        self,
        process_cnj: str,
        movement_id: str
    ) -> Optional[ProcessMovement]:
        """
        Get a specific movement by its ID and process CNJ.
        
        Args:
            process_cnj: CNJ formatted process number
            movement_id: Movement ID
            
        Returns:
            Process movement object if found, None otherwise
            
        Raises:
            DatabaseError: If any database error occurs
        """
        movements = await self.get_all(
            filter_query={"process_cnj": process_cnj, "movement_id": movement_id},
            limit=1
        )
        
        return movements[0] if movements else None
    
    async def get_by_date_range(
        self,
        process_cnj: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100
    ) -> List[ProcessMovement]:
        """
        Get movements for a specific process within a date range.
        
        Args:
            process_cnj: CNJ formatted process number
            start_date: Start date for the range
            end_date: End date for the range
            limit: Maximum number of movements to return
            
        Returns:
            List of process movement objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={
                "process_cnj": process_cnj,
                "date": {"$gte": start_date, "$lte": end_date}
            },
            sort=[("date", -1)],
            limit=limit
        )
    
    async def get_by_type(
        self,
        process_cnj: str,
        movement_type: MovementType,
        limit: int = 100
    ) -> List[ProcessMovement]:
        """
        Get movements for a specific process with a specific type.
        
        Args:
            process_cnj: CNJ formatted process number
            movement_type: Type of movement to filter by
            limit: Maximum number of movements to return
            
        Returns:
            List of process movement objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={"process_cnj": process_cnj, "type": movement_type},
            sort=[("date", -1)],
            limit=limit
        )
    
    async def get_by_importance(
        self,
        process_cnj: str,
        importance: MovementImportance,
        limit: int = 100
    ) -> List[ProcessMovement]:
        """
        Get movements for a specific process with a specific importance level.
        
        Args:
            process_cnj: CNJ formatted process number
            importance: Importance level to filter by
            limit: Maximum number of movements to return
            
        Returns:
            List of process movement objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={"process_cnj": process_cnj, "importance": importance},
            sort=[("date", -1)],
            limit=limit
        )
    
    async def mark_as_notified(
        self,
        movement_id: Union[str, ObjectId]
    ) -> Optional[ProcessMovement]:
        """
        Mark a movement as notified.
        
        Args:
            movement_id: Movement ID
            
        Returns:
            Updated process movement object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Convert string ID to ObjectId if needed
            doc_id = ObjectId(movement_id) if isinstance(movement_id, str) else movement_id
            
            # Update the document
            result = await self.collection.update_one(
                {"_id": doc_id},
                {
                    "$set": {
                        "notified": True,
                        "last_notification_date": datetime.utcnow()
                    },
                    "$inc": {"notification_count": 1}
                }
            )
            
            # Check if document was found and updated
            if result.matched_count == 0:
                return None
            
            # Get the updated document
            updated_doc = await self.collection.find_one({"_id": doc_id})
            if not updated_doc:
                return None
            
            # Convert to Pydantic model and return
            return self.model(**updated_doc)
            
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.mark_as_notified: {e}")
            raise DatabaseError(f"Failed to mark movement as notified: {e}")
    
    async def get_unnotified_movements(
        self,
        process_cnj: str,
        limit: int = 100
    ) -> List[ProcessMovement]:
        """
        Get unnotified movements for a specific process.
        
        Args:
            process_cnj: CNJ formatted process number
            limit: Maximum number of movements to return
            
        Returns:
            List of unnotified process movement objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={"process_cnj": process_cnj, "notified": False},
            sort=[("date", -1)],
            limit=limit
        )
    
    async def get_recent_movements(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> List[ProcessMovement]:
        """
        Get recent movements across all processes.
        
        Args:
            hours: Number of hours to look back
            limit: Maximum number of movements to return
            
        Returns:
            List of recent process movement objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        return await self.get_all(
            filter_query={"date": {"$gte": cutoff_time}},
            sort=[("date", -1)],
            limit=limit
        )
    
    async def get_latest_movement(self, process_cnj: str) -> Optional[ProcessMovement]:
        """
        Get the latest movement for a specific process.
        
        Args:
            process_cnj: CNJ formatted process number
            
        Returns:
            Latest process movement object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        movements = await self.get_all(
            filter_query={"process_cnj": process_cnj},
            sort=[("date", -1)],
            limit=1
        )
        
        return movements[0] if movements else None
    
    async def update_importance(
        self,
        movement_id: Union[str, ObjectId],
        importance: MovementImportance
    ) -> Optional[ProcessMovement]:
        """
        Update a movement's importance level.
        
        Args:
            movement_id: Movement ID
            importance: New importance level
            
        Returns:
            Updated process movement object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.update(movement_id, {"importance": importance})
    
    async def update_is_terminal(
        self,
        movement_id: Union[str, ObjectId],
        is_terminal: bool
    ) -> Optional[ProcessMovement]:
        """
        Update whether a movement is terminal (concludes the process or a phase).
        
        Args:
            movement_id: Movement ID
            is_terminal: Whether the movement is terminal
            
        Returns:
            Updated process movement object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.update(movement_id, {"is_terminal": is_terminal})
    
    async def update_extracted_info(
        self,
        movement_id: Union[str, ObjectId],
        extracted_dates: Optional[List[datetime]] = None,
        extracted_values: Optional[Dict[str, float]] = None,
        extracted_entities: Optional[Dict[str, List[str]]] = None
    ) -> Optional[ProcessMovement]:
        """
        Update a movement's extracted information.
        
        Args:
            movement_id: Movement ID
            extracted_dates: Dates extracted from the movement content
            extracted_values: Monetary values extracted from the movement content
            extracted_entities: Named entities extracted from the movement content
            
        Returns:
            Updated process movement object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        update_data = {}
        
        if extracted_dates is not None:
            update_data["extracted_dates"] = extracted_dates
        
        if extracted_values is not None:
            update_data["extracted_values"] = extracted_values
        
        if extracted_entities is not None:
            update_data["extracted_entities"] = extracted_entities
        
        return await self.update(movement_id, update_data)
    
    async def count_movements_by_process(self, process_cnj: str) -> int:
        """
        Count the number of movements for a specific process.
        
        Args:
            process_cnj: CNJ formatted process number
            
        Returns:
            Number of movements
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.count(filter_query={"process_cnj": process_cnj})
    
    async def count_movements_by_type(
        self,
        process_cnj: str,
        movement_type: MovementType
    ) -> int:
        """
        Count the number of movements of a specific type for a specific process.
        
        Args:
            process_cnj: CNJ formatted process number
            movement_type: Type of movement to count
            
        Returns:
            Number of movements
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.count(
            filter_query={"process_cnj": process_cnj, "type": movement_type}
        )
    
    async def delete_by_process_cnj(self, process_cnj: str) -> int:
        """
        Delete all movements for a specific process.
        
        Args:
            process_cnj: CNJ formatted process number
            
        Returns:
            Number of movements deleted
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.bulk_delete(filter_query={"process_cnj": process_cnj})
