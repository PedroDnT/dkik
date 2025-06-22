"""
Database package initialization.

This module initializes the MongoDB connection and imports database operations
for all models to make them easily accessible throughout the application.
"""
import logging
from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from app.config import settings

# Configure logger
logger = logging.getLogger(__name__)

# Global database connection
client: Optional[AsyncIOMotorClient] = None
db: Optional[AsyncIOMotorDatabase] = None


async def connect_to_mongo() -> None:
    """
    Create a connection to the MongoDB database.
    
    This function establishes an async connection to MongoDB using Motor.
    It should be called during application startup.
    """
    global client, db
    
    try:
        logger.info("Connecting to MongoDB...")
        client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=5000
        )
        
        # Verify connection is working
        await client.admin.command('ping')
        
        db = client[settings.MONGODB_DB_NAME]
        logger.info(f"Connected to MongoDB database: {settings.MONGODB_DB_NAME}")
        
        # Initialize database indexes
        await create_indexes()
        
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


async def close_mongo_connection() -> None:
    """
    Close the MongoDB connection.
    
    This function closes the connection to MongoDB.
    It should be called during application shutdown.
    """
    global client
    if client:
        logger.info("Closing MongoDB connection...")
        client.close()
        logger.info("MongoDB connection closed")


async def create_indexes() -> None:
    """
    Create indexes for collections to optimize queries.
    
    This function creates indexes for all collections in the database.
    It should be called during application startup after connecting to MongoDB.
    """
    if not db:
        logger.warning("Cannot create indexes: database connection not established")
        return
    
    logger.info("Creating database indexes...")
    
    # User collection indexes
    await db.users.create_index("phone_number", unique=True)
    await db.users.create_index("email", sparse=True)
    await db.users.create_index("subscription_status")
    
    # Process collection indexes
    await db.processes.create_index("cnj_number", unique=True)
    await db.processes.create_index("status")
    await db.processes.create_index("last_movement_date")
    await db.processes.create_index("is_tracked")
    
    # Subscription collection indexes
    await db.subscriptions.create_index([("user_id", 1), ("process_cnj", 1)], unique=True)
    await db.subscriptions.create_index("user_id")
    await db.subscriptions.create_index("process_cnj")
    await db.subscriptions.create_index("is_active")
    
    # Process Movement collection indexes
    await db.process_movements.create_index([("process_cnj", 1), ("movement_id", 1)], unique=True)
    await db.process_movements.create_index("process_cnj")
    await db.process_movements.create_index("date")
    await db.process_movements.create_index("type")
    
    # Notification collection indexes
    await db.notifications.create_index("user_id")
    await db.notifications.create_index("phone_number")
    await db.notifications.create_index("process_cnj", sparse=True)
    await db.notifications.create_index("delivery_status")
    await db.notifications.create_index("sent_at", sparse=True)
    
    logger.info("Database indexes created successfully")


async def get_database() -> AsyncIOMotorDatabase:
    """
    Get the database instance.
    
    This function returns the database instance for use in dependency injection.
    """
    if not db:
        await connect_to_mongo()
    return db


# Import database operations
from app.database.users import UserDB
from app.database.processes import ProcessDB
from app.database.subscriptions import SubscriptionDB
from app.database.process_movements import ProcessMovementDB
from app.database.notifications import NotificationDB

# Export database operations
__all__ = [
    "connect_to_mongo",
    "close_mongo_connection",
    "get_database",
    "UserDB",
    "ProcessDB",
    "SubscriptionDB",
    "ProcessMovementDB",
    "NotificationDB",
]
