"""
Process database operations for the DKIK WhatsApp Bot.

This module provides a ProcessDB class that extends BaseDB to handle
process-specific database operations such as finding processes by CNJ number,
updating process status, and managing process movements and hearings.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from bson import ObjectId
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.database.base import BaseDB, DatabaseError, DocumentNotFoundError, DuplicateDocumentError
from app.models.process import Process, ProcessStatus, ProcessType, ProcessSecrecy

# Configure logger
logger = logging.getLogger(__name__)


class ProcessDB(BaseDB[Process, Process, Process]):
    """
    Process database operations class.
    
    This class extends BaseDB to provide process-specific database operations
    such as finding processes by CNJ number, updating process status,
    and managing process movements and hearings.
    """
    
    async def get_by_cnj_number(self, cnj_number: str) -> Optional[Process]:
        """
        Get a process by CNJ number.
        
        Args:
            cnj_number: CNJ formatted process number
            
        Returns:
            Process object if found, None otherwise
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_by_field("cnj_number", cnj_number)
    
    async def update_status(
        self,
        cnj_number: str,
        status: ProcessStatus
    ) -> Optional[Process]:
        """
        Update a process status.
        
        Args:
            cnj_number: CNJ formatted process number
            status: New process status
            
        Returns:
            Updated process object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.update_by_field(
            "cnj_number",
            cnj_number,
            {"status": status}
        )
    
    async def update_last_movement(
        self,
        cnj_number: str,
        movement_date: datetime,
        movement_description: str,
        movement_id: str
    ) -> Optional[Process]:
        """
        Update a process's last movement information.
        
        Args:
            cnj_number: CNJ formatted process number
            movement_date: Date of the last movement
            movement_description: Description of the last movement
            movement_id: ID of the last movement
            
        Returns:
            Updated process object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        update_data = {
            "last_movement_date": movement_date,
            "last_movement_description": movement_description,
            "last_movement_id": movement_id,
            "last_checked": datetime.utcnow()
        }
        
        return await self.update_by_field("cnj_number", cnj_number, update_data)
    
    async def add_hearing(
        self,
        cnj_number: str,
        hearing_data: Dict[str, Any]
    ) -> Optional[Process]:
        """
        Add a hearing to a process.
        
        Args:
            cnj_number: CNJ formatted process number
            hearing_data: Hearing data to add
            
        Returns:
            Updated process object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Validate required fields
            required_fields = ["date", "type", "location"]
            for field in required_fields:
                if field not in hearing_data:
                    raise ValueError(f"Hearing missing required field: {field}")
            
            # Convert string ID to ObjectId if needed
            result = await self.collection.update_one(
                {"cnj_number": cnj_number},
                {"$push": {"hearings": hearing_data}}
            )
            
            # Check if document was found and updated
            if result.matched_count == 0:
                return None
            
            # Get the updated document
            updated_doc = await self.collection.find_one({"cnj_number": cnj_number})
            if not updated_doc:
                return None
            
            # Convert to Pydantic model and return
            return self.model(**updated_doc)
            
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.add_hearing: {e}")
            raise DatabaseError(f"Failed to add hearing: {e}")
    
    async def update_tracking_status(
        self,
        cnj_number: str,
        is_tracked: bool,
        increment: bool = True
    ) -> Optional[Process]:
        """
        Update a process's tracking status.
        
        Args:
            cnj_number: CNJ formatted process number
            is_tracked: Whether the process is being tracked
            increment: Whether to increment or decrement the tracking count
            
        Returns:
            Updated process object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Prepare update operation
            update_data = {"is_tracked": is_tracked}
            
            # Increment or decrement tracking count
            inc_value = 1 if increment else -1
            
            # Update the document
            result = await self.collection.update_one(
                {"cnj_number": cnj_number},
                {
                    "$set": update_data,
                    "$inc": {"tracking_count": inc_value}
                }
            )
            
            # Check if document was found and updated
            if result.matched_count == 0:
                return None
            
            # Get the updated document
            updated_doc = await self.collection.find_one({"cnj_number": cnj_number})
            if not updated_doc:
                return None
            
            # Convert to Pydantic model and return
            return self.model(**updated_doc)
            
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.update_tracking_status: {e}")
            raise DatabaseError(f"Failed to update tracking status: {e}")
    
    async def update_secrecy_level(
        self,
        cnj_number: str,
        secrecy_level: ProcessSecrecy
    ) -> Optional[Process]:
        """
        Update a process's secrecy level.
        
        Args:
            cnj_number: CNJ formatted process number
            secrecy_level: New secrecy level
            
        Returns:
            Updated process object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.update_by_field(
            "cnj_number",
            cnj_number,
            {"secrecy_level": secrecy_level}
        )
    
    async def update_parties(
        self,
        cnj_number: str,
        parties: List[Dict[str, Any]]
    ) -> Optional[Process]:
        """
        Update a process's parties information.
        
        Args:
            cnj_number: CNJ formatted process number
            parties: List of parties data
            
        Returns:
            Updated process object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        # Validate parties data
        for party in parties:
            required_fields = ["role", "name"]
            for field in required_fields:
                if field not in party:
                    raise ValueError(f"Party missing required field: {field}")
        
        return await self.update_by_field(
            "cnj_number",
            cnj_number,
            {"parties": parties}
        )
    
    async def get_tracked_processes(self) -> List[Process]:
        """
        Get all processes that are being tracked.
        
        Returns:
            List of tracked process objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={"is_tracked": True}
        )
    
    async def get_processes_with_hearings(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Process]:
        """
        Get processes with hearings scheduled between start_date and end_date.
        
        Args:
            start_date: Start date for hearing range
            end_date: End date for hearing range
            
        Returns:
            List of process objects with hearings in the date range
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Find processes with hearings in the date range
            pipeline = [
                {
                    "$match": {
                        "hearings": {
                            "$elemMatch": {
                                "date": {
                                    "$gte": start_date,
                                    "$lte": end_date
                                }
                            }
                        }
                    }
                }
            ]
            
            # Execute aggregation
            cursor = self.collection.aggregate(pipeline)
            
            # Convert cursor to list of Pydantic models
            result = []
            async for doc in cursor:
                result.append(self.model(**doc))
            
            return result
            
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.get_processes_with_hearings: {e}")
            raise DatabaseError(f"Failed to get processes with hearings: {e}")
    
    async def update_datajud_metadata(
        self,
        cnj_number: str,
        metadata: Dict[str, Any]
    ) -> Optional[Process]:
        """
        Update a process's DataJud metadata.
        
        Args:
            cnj_number: CNJ formatted process number
            metadata: DataJud metadata
            
        Returns:
            Updated process object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.update_by_field(
            "cnj_number",
            cnj_number,
            {"datajud_metadata": metadata}
        )
    
    async def mark_as_checked(
        self,
        cnj_number: str
    ) -> Optional[Process]:
        """
        Mark a process as checked (update last_checked timestamp).
        
        Args:
            cnj_number: CNJ formatted process number
            
        Returns:
            Updated process object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.update_by_field(
            "cnj_number",
            cnj_number,
            {"last_checked": datetime.utcnow()}
        )
    
    async def get_processes_to_check(
        self,
        max_age_minutes: int = 60
    ) -> List[Process]:
        """
        Get tracked processes that haven't been checked recently.
        
        Args:
            max_age_minutes: Maximum age in minutes since last check
            
        Returns:
            List of process objects to check
            
        Raises:
            DatabaseError: If any database error occurs
        """
        cutoff_time = datetime.utcnow() - datetime.timedelta(minutes=max_age_minutes)
        
        return await self.get_all(
            filter_query={
                "is_tracked": True,
                "last_checked": {"$lt": cutoff_time}
            }
        )
    
    async def get_processes_by_status(
        self,
        status: ProcessStatus
    ) -> List[Process]:
        """
        Get processes with a specific status.
        
        Args:
            status: Process status to filter by
            
        Returns:
            List of process objects with the specified status
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={"status": status}
        )
    
    async def get_processes_by_court(
        self,
        court_code: str
    ) -> List[Process]:
        """
        Get processes from a specific court.
        
        Args:
            court_code: Court code to filter by
            
        Returns:
            List of process objects from the specified court
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={"court.code": court_code}
        )
