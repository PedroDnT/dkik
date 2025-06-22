"""
Base MongoDB database operations class.

This module provides a base class for MongoDB database operations with common CRUD
functionality that can be inherited by specific model database operation classes.
"""
import logging
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union, cast
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError
from pydantic import BaseModel

from app.models.base import MongoBaseModel

# Configure logger
logger = logging.getLogger(__name__)

# Generic type for Pydantic models
ModelType = TypeVar("ModelType", bound=MongoBaseModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class DatabaseError(Exception):
    """Base exception for database operations."""
    pass


class DocumentNotFoundError(DatabaseError):
    """Exception raised when a document is not found."""
    pass


class DuplicateDocumentError(DatabaseError):
    """Exception raised when a duplicate document is detected."""
    pass


class BaseDB(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Base class for database operations.
    
    This class provides common CRUD operations for MongoDB collections
    and should be inherited by specific model database operation classes.
    
    Attributes:
        collection_name: Name of the MongoDB collection
        model: Pydantic model class for documents in this collection
    """
    
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        collection_name: str,
        model: Type[ModelType]
    ):
        """
        Initialize the database operations class.
        
        Args:
            db: AsyncIOMotorDatabase instance
            collection_name: Name of the MongoDB collection
            model: Pydantic model class for documents in this collection
        """
        self.db = db
        self.collection_name = collection_name
        self.collection: AsyncIOMotorCollection = db[collection_name]
        self.model = model
    
    async def create(self, obj_in: Union[CreateSchemaType, Dict[str, Any]]) -> ModelType:
        """
        Create a new document in the collection.
        
        Args:
            obj_in: Document data as Pydantic model or dict
            
        Returns:
            Created document as a Pydantic model
            
        Raises:
            DuplicateDocumentError: If a document with the same unique key already exists
            DatabaseError: If any other database error occurs
        """
        try:
            # Convert to dict if it's a Pydantic model
            obj_data = obj_in.dict() if hasattr(obj_in, "dict") else obj_in
            
            # Insert document
            result = await self.collection.insert_one(obj_data)
            
            # Get the created document
            created_doc = await self.collection.find_one({"_id": result.inserted_id})
            if not created_doc:
                raise DatabaseError("Failed to retrieve created document")
            
            # Convert to Pydantic model and return
            return self.model(**created_doc)
            
        except DuplicateKeyError as e:
            logger.error(f"Duplicate key error in {self.collection_name}: {e}")
            raise DuplicateDocumentError(f"Document already exists: {e}")
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.create: {e}")
            raise DatabaseError(f"Failed to create document: {e}")
    
    async def get(
        self, 
        id: Union[str, ObjectId], 
        projection: Optional[Dict[str, Any]] = None
    ) -> Optional[ModelType]:
        """
        Get a document by ID.
        
        Args:
            id: Document ID as string or ObjectId
            projection: Optional projection to include/exclude fields
            
        Returns:
            Document as a Pydantic model or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Convert string ID to ObjectId if needed
            doc_id = ObjectId(id) if isinstance(id, str) else id
            
            # Find document
            doc = await self.collection.find_one({"_id": doc_id}, projection)
            if not doc:
                return None
            
            # Convert to Pydantic model and return
            return self.model(**doc)
            
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.get: {e}")
            raise DatabaseError(f"Failed to get document: {e}")
    
    async def get_by_field(
        self,
        field: str,
        value: Any,
        projection: Optional[Dict[str, Any]] = None
    ) -> Optional[ModelType]:
        """
        Get a document by a specific field value.
        
        Args:
            field: Field name to query
            value: Field value to match
            projection: Optional projection to include/exclude fields
            
        Returns:
            Document as a Pydantic model or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Find document
            doc = await self.collection.find_one({field: value}, projection)
            if not doc:
                return None
            
            # Convert to Pydantic model and return
            return self.model(**doc)
            
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.get_by_field: {e}")
            raise DatabaseError(f"Failed to get document by field: {e}")
    
    async def get_all(
        self,
        filter_query: Optional[Dict[str, Any]] = None,
        projection: Optional[Dict[str, Any]] = None,
        sort: Optional[List[tuple]] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """
        Get multiple documents with filtering, sorting, and pagination.
        
        Args:
            filter_query: MongoDB filter query
            projection: Optional projection to include/exclude fields
            sort: List of (field, direction) tuples for sorting
            skip: Number of documents to skip (for pagination)
            limit: Maximum number of documents to return
            
        Returns:
            List of documents as Pydantic models
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Prepare query
            filter_query = filter_query or {}
            cursor = self.collection.find(filter_query, projection)
            
            # Apply sorting if provided
            if sort:
                cursor = cursor.sort(sort)
            
            # Apply pagination
            cursor = cursor.skip(skip).limit(limit)
            
            # Execute query and convert results to list of Pydantic models
            result = []
            async for doc in cursor:
                result.append(self.model(**doc))
            
            return result
            
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.get_all: {e}")
            raise DatabaseError(f"Failed to get documents: {e}")
    
    async def count(self, filter_query: Optional[Dict[str, Any]] = None) -> int:
        """
        Count documents matching a filter query.
        
        Args:
            filter_query: MongoDB filter query
            
        Returns:
            Number of matching documents
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            filter_query = filter_query or {}
            return await self.collection.count_documents(filter_query)
            
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.count: {e}")
            raise DatabaseError(f"Failed to count documents: {e}")
    
    async def update(
        self,
        id: Union[str, ObjectId],
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> Optional[ModelType]:
        """
        Update a document by ID.
        
        Args:
            id: Document ID as string or ObjectId
            obj_in: Update data as Pydantic model or dict
            
        Returns:
            Updated document as a Pydantic model or None if not found
            
        Raises:
            DuplicateDocumentError: If update violates a unique constraint
            DatabaseError: If any other database error occurs
        """
        try:
            # Convert string ID to ObjectId if needed
            doc_id = ObjectId(id) if isinstance(id, str) else id
            
            # Convert to dict if it's a Pydantic model
            update_data = obj_in.dict(exclude_unset=True) if hasattr(obj_in, "dict") else obj_in
            
            # Remove id field if present to avoid modification attempts
            if "_id" in update_data:
                del update_data["_id"]
            
            # Update document
            result = await self.collection.update_one(
                {"_id": doc_id},
                {"$set": update_data}
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
            
        except DuplicateKeyError as e:
            logger.error(f"Duplicate key error in {self.collection_name}.update: {e}")
            raise DuplicateDocumentError(f"Update would create duplicate: {e}")
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.update: {e}")
            raise DatabaseError(f"Failed to update document: {e}")
    
    async def update_by_field(
        self,
        field: str,
        value: Any,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> Optional[ModelType]:
        """
        Update a document by a specific field value.
        
        Args:
            field: Field name to query
            value: Field value to match
            obj_in: Update data as Pydantic model or dict
            
        Returns:
            Updated document as a Pydantic model or None if not found
            
        Raises:
            DuplicateDocumentError: If update violates a unique constraint
            DatabaseError: If any other database error occurs
        """
        try:
            # Convert to dict if it's a Pydantic model
            update_data = obj_in.dict(exclude_unset=True) if hasattr(obj_in, "dict") else obj_in
            
            # Remove id field if present to avoid modification attempts
            if "_id" in update_data:
                del update_data["_id"]
            
            # Update document
            result = await self.collection.update_one(
                {field: value},
                {"$set": update_data}
            )
            
            # Check if document was found and updated
            if result.matched_count == 0:
                return None
            
            # Get the updated document
            updated_doc = await self.collection.find_one({field: value})
            if not updated_doc:
                return None
            
            # Convert to Pydantic model and return
            return self.model(**updated_doc)
            
        except DuplicateKeyError as e:
            logger.error(f"Duplicate key error in {self.collection_name}.update_by_field: {e}")
            raise DuplicateDocumentError(f"Update would create duplicate: {e}")
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.update_by_field: {e}")
            raise DatabaseError(f"Failed to update document: {e}")
    
    async def delete(self, id: Union[str, ObjectId]) -> bool:
        """
        Delete a document by ID.
        
        Args:
            id: Document ID as string or ObjectId
            
        Returns:
            True if document was deleted, False if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Convert string ID to ObjectId if needed
            doc_id = ObjectId(id) if isinstance(id, str) else id
            
            # Delete document
            result = await self.collection.delete_one({"_id": doc_id})
            
            # Return whether a document was deleted
            return result.deleted_count > 0
            
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.delete: {e}")
            raise DatabaseError(f"Failed to delete document: {e}")
    
    async def delete_by_field(self, field: str, value: Any) -> bool:
        """
        Delete a document by a specific field value.
        
        Args:
            field: Field name to query
            value: Field value to match
            
        Returns:
            True if document was deleted, False if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Delete document
            result = await self.collection.delete_one({field: value})
            
            # Return whether a document was deleted
            return result.deleted_count > 0
            
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.delete_by_field: {e}")
            raise DatabaseError(f"Failed to delete document: {e}")
    
    async def bulk_create(self, objs_in: List[Union[CreateSchemaType, Dict[str, Any]]]) -> List[ModelType]:
        """
        Create multiple documents in the collection.
        
        Args:
            objs_in: List of document data as Pydantic models or dicts
            
        Returns:
            List of created documents as Pydantic models
            
        Raises:
            DuplicateDocumentError: If any document has a duplicate key
            DatabaseError: If any other database error occurs
        """
        try:
            # Convert to dicts if they're Pydantic models
            objs_data = [
                obj.dict() if hasattr(obj, "dict") else obj
                for obj in objs_in
            ]
            
            # Insert documents
            result = await self.collection.insert_many(objs_data)
            
            # Get the created documents
            created_docs = await self.collection.find(
                {"_id": {"$in": list(result.inserted_ids)}}
            ).to_list(length=len(result.inserted_ids))
            
            # Convert to Pydantic models and return
            return [self.model(**doc) for doc in created_docs]
            
        except DuplicateKeyError as e:
            logger.error(f"Duplicate key error in {self.collection_name}.bulk_create: {e}")
            raise DuplicateDocumentError(f"One or more documents already exist: {e}")
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.bulk_create: {e}")
            raise DatabaseError(f"Failed to create documents: {e}")
    
    async def bulk_update(
        self,
        filter_query: Dict[str, Any],
        update_data: Dict[str, Any]
    ) -> int:
        """
        Update multiple documents matching a filter query.
        
        Args:
            filter_query: MongoDB filter query
            update_data: Update data as dict
            
        Returns:
            Number of documents updated
            
        Raises:
            DuplicateDocumentError: If update violates a unique constraint
            DatabaseError: If any other database error occurs
        """
        try:
            # Update documents
            result = await self.collection.update_many(
                filter_query,
                {"$set": update_data}
            )
            
            # Return number of documents updated
            return result.modified_count
            
        except DuplicateKeyError as e:
            logger.error(f"Duplicate key error in {self.collection_name}.bulk_update: {e}")
            raise DuplicateDocumentError(f"Update would create duplicates: {e}")
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.bulk_update: {e}")
            raise DatabaseError(f"Failed to update documents: {e}")
    
    async def bulk_delete(self, filter_query: Dict[str, Any]) -> int:
        """
        Delete multiple documents matching a filter query.
        
        Args:
            filter_query: MongoDB filter query
            
        Returns:
            Number of documents deleted
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Delete documents
            result = await self.collection.delete_many(filter_query)
            
            # Return number of documents deleted
            return result.deleted_count
            
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.bulk_delete: {e}")
            raise DatabaseError(f"Failed to delete documents: {e}")
    
    async def exists(self, filter_query: Dict[str, Any]) -> bool:
        """
        Check if any document matches the filter query.
        
        Args:
            filter_query: MongoDB filter query
            
        Returns:
            True if matching document exists, False otherwise
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Count documents with limit=1 for efficiency
            count = await self.collection.count_documents(filter_query, limit=1)
            return count > 0
            
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.exists: {e}")
            raise DatabaseError(f"Failed to check document existence: {e}")
    
    async def aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute an aggregation pipeline.
        
        Args:
            pipeline: MongoDB aggregation pipeline
            
        Returns:
            List of aggregation results
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Execute aggregation pipeline
            cursor = self.collection.aggregate(pipeline)
            
            # Convert cursor to list and return
            return await cursor.to_list(length=None)
            
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.aggregate: {e}")
            raise DatabaseError(f"Failed to execute aggregation: {e}")
