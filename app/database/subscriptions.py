"""
Subscription database operations for the DKIK WhatsApp Bot.

This module provides a SubscriptionDB class that extends BaseDB to handle
subscription-specific database operations such as finding subscriptions by user ID,
managing tracking preferences, and handling notification settings.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from bson import ObjectId
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.database.base import BaseDB, DatabaseError, DocumentNotFoundError, DuplicateDocumentError
from app.models.subscription import Subscription, TrackingType, NotificationFrequency

# Configure logger
logger = logging.getLogger(__name__)


class SubscriptionDB(BaseDB[Subscription, Subscription, Subscription]):
    """
    Subscription database operations class.
    
    This class extends BaseDB to provide subscription-specific database operations
    such as finding subscriptions by user ID, managing tracking preferences,
    and handling notification settings.
    """
    
    async def get_by_user_id(self, user_id: str) -> List[Subscription]:
        """
        Get all subscriptions for a specific user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of subscription objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(filter_query={"user_id": user_id})
    
    async def get_by_process_cnj(self, process_cnj: str) -> List[Subscription]:
        """
        Get all subscriptions for a specific process.
        
        Args:
            process_cnj: CNJ formatted process number
            
        Returns:
            List of subscription objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(filter_query={"process_cnj": process_cnj})
    
    async def get_by_user_and_process(
        self,
        user_id: str,
        process_cnj: str
    ) -> Optional[Subscription]:
        """
        Get a subscription by user ID and process CNJ number.
        
        Args:
            user_id: User ID
            process_cnj: CNJ formatted process number
            
        Returns:
            Subscription object if found, None otherwise
            
        Raises:
            DatabaseError: If any database error occurs
        """
        subscriptions = await self.get_all(
            filter_query={"user_id": user_id, "process_cnj": process_cnj},
            limit=1
        )
        
        return subscriptions[0] if subscriptions else None
    
    async def update_tracking_types(
        self,
        subscription_id: Union[str, ObjectId],
        tracking_types: List[TrackingType]
    ) -> Optional[Subscription]:
        """
        Update a subscription's tracking types.
        
        Args:
            subscription_id: Subscription ID
            tracking_types: List of tracking types
            
        Returns:
            Updated subscription object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.update(subscription_id, {"tracking_types": tracking_types})
    
    async def update_notification_frequency(
        self,
        subscription_id: Union[str, ObjectId],
        frequency: NotificationFrequency
    ) -> Optional[Subscription]:
        """
        Update a subscription's notification frequency.
        
        Args:
            subscription_id: Subscription ID
            frequency: New notification frequency
            
        Returns:
            Updated subscription object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.update(subscription_id, {"notification_frequency": frequency})
    
    async def update_notification_channels(
        self,
        subscription_id: Union[str, ObjectId],
        channels: List[str]
    ) -> Optional[Subscription]:
        """
        Update a subscription's notification channels.
        
        Args:
            subscription_id: Subscription ID
            channels: List of notification channels
            
        Returns:
            Updated subscription object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.update(subscription_id, {"notification_channels": channels})
    
    async def update_is_active(
        self,
        subscription_id: Union[str, ObjectId],
        is_active: bool
    ) -> Optional[Subscription]:
        """
        Update a subscription's active status.
        
        Args:
            subscription_id: Subscription ID
            is_active: Whether the subscription is active
            
        Returns:
            Updated subscription object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.update(subscription_id, {"is_active": is_active})
    
    async def update_last_notification(
        self,
        subscription_id: Union[str, ObjectId],
        movement_id: str
    ) -> Optional[Subscription]:
        """
        Update a subscription's last notification information.
        
        Args:
            subscription_id: Subscription ID
            movement_id: ID of the last movement that triggered a notification
            
        Returns:
            Updated subscription object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        update_data = {
            "last_notification_sent": datetime.utcnow(),
            "last_movement_notified": movement_id,
            "notifications_sent_total": {"$inc": 1}
        }
        
        try:
            # Convert string ID to ObjectId if needed
            doc_id = ObjectId(subscription_id) if isinstance(subscription_id, str) else subscription_id
            
            # Update the document
            result = await self.collection.update_one(
                {"_id": doc_id},
                {
                    "$set": {
                        "last_notification_sent": datetime.utcnow(),
                        "last_movement_notified": movement_id
                    },
                    "$inc": {"notifications_sent_total": 1}
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
            logger.error(f"Database error in {self.collection_name}.update_last_notification: {e}")
            raise DatabaseError(f"Failed to update last notification: {e}")
    
    async def increment_notifications_sent_today(
        self,
        subscription_id: Union[str, ObjectId]
    ) -> Optional[Subscription]:
        """
        Increment a subscription's notifications_sent_today counter.
        
        Args:
            subscription_id: Subscription ID
            
        Returns:
            Updated subscription object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Convert string ID to ObjectId if needed
            doc_id = ObjectId(subscription_id) if isinstance(subscription_id, str) else subscription_id
            
            # Update the document using $inc operator
            result = await self.collection.update_one(
                {"_id": doc_id},
                {"$inc": {"notifications_sent_today": 1}}
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
            logger.error(f"Database error in {self.collection_name}.increment_notifications_sent_today: {e}")
            raise DatabaseError(f"Failed to increment notifications sent today: {e}")
    
    async def reset_notifications_sent_today(self) -> int:
        """
        Reset notifications_sent_today counter for all subscriptions.
        
        This method should be called once per day to reset the daily notification counter.
        
        Returns:
            Number of subscriptions updated
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Update all documents
            result = await self.collection.update_many(
                {},
                {"$set": {"notifications_sent_today": 0}}
            )
            
            # Return number of documents updated
            return result.modified_count
            
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.reset_notifications_sent_today: {e}")
            raise DatabaseError(f"Failed to reset notifications sent today: {e}")
    
    async def update_keywords(
        self,
        subscription_id: Union[str, ObjectId],
        movement_keywords: Optional[List[str]] = None,
        exclude_keywords: Optional[List[str]] = None
    ) -> Optional[Subscription]:
        """
        Update a subscription's keyword filters.
        
        Args:
            subscription_id: Subscription ID
            movement_keywords: Keywords to filter movements by
            exclude_keywords: Keywords to exclude movements by
            
        Returns:
            Updated subscription object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        update_data = {}
        
        if movement_keywords is not None:
            update_data["movement_keywords"] = movement_keywords
        
        if exclude_keywords is not None:
            update_data["exclude_keywords"] = exclude_keywords
        
        return await self.update(subscription_id, update_data)
    
    async def update_importance(
        self,
        subscription_id: Union[str, ObjectId],
        importance: int
    ) -> Optional[Subscription]:
        """
        Update a subscription's importance level.
        
        Args:
            subscription_id: Subscription ID
            importance: Importance level (1-5)
            
        Returns:
            Updated subscription object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
            ValueError: If importance is not between 1 and 5
        """
        if not 1 <= importance <= 5:
            raise ValueError("Importance must be between 1 and 5")
        
        return await self.update(subscription_id, {"importance": importance})
    
    async def update_expiration(
        self,
        subscription_id: Union[str, ObjectId],
        expires_at: Optional[datetime]
    ) -> Optional[Subscription]:
        """
        Update a subscription's expiration date.
        
        Args:
            subscription_id: Subscription ID
            expires_at: When the subscription expires, or None for no expiration
            
        Returns:
            Updated subscription object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.update(subscription_id, {"expires_at": expires_at})
    
    async def get_active_subscriptions(self) -> List[Subscription]:
        """
        Get all active subscriptions.
        
        Returns:
            List of active subscription objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(filter_query={"is_active": True})
    
    async def get_expired_subscriptions(self) -> List[Subscription]:
        """
        Get all expired subscriptions.
        
        Returns:
            List of expired subscription objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={
                "expires_at": {"$lt": datetime.utcnow()},
                "is_active": True
            }
        )
    
    async def get_subscriptions_by_notification_frequency(
        self,
        frequency: NotificationFrequency
    ) -> List[Subscription]:
        """
        Get all subscriptions with a specific notification frequency.
        
        Args:
            frequency: Notification frequency to filter by
            
        Returns:
            List of subscription objects with the specified frequency
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={"notification_frequency": frequency, "is_active": True}
        )
    
    async def count_user_subscriptions(self, user_id: str) -> int:
        """
        Count the number of subscriptions for a specific user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of subscriptions
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.count(filter_query={"user_id": user_id})
    
    async def count_process_subscriptions(self, process_cnj: str) -> int:
        """
        Count the number of subscriptions for a specific process.
        
        Args:
            process_cnj: CNJ formatted process number
            
        Returns:
            Number of subscriptions
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.count(filter_query={"process_cnj": process_cnj})
