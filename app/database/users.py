"""
User database operations for the DKIK WhatsApp Bot.

This module provides a UserDB class that extends BaseDB to handle
user-specific database operations such as finding users by phone number,
updating subscription status, and managing user preferences.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from bson import ObjectId
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.database.base import BaseDB, DatabaseError, DocumentNotFoundError, DuplicateDocumentError
from app.models.user import User, SubscriptionStatus, SubscriptionTier, Language, NotificationPreference

# Configure logger
logger = logging.getLogger(__name__)


class UserDB(BaseDB[User, User, User]):
    """
    User database operations class.
    
    This class extends BaseDB to provide user-specific database operations
    such as finding users by phone number, updating subscription status,
    and managing user preferences.
    """
    
    async def get_by_phone_number(self, phone_number: str) -> Optional[User]:
        """
        Get a user by phone number.
        
        Args:
            phone_number: User's WhatsApp phone number
            
        Returns:
            User object if found, None otherwise
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_by_field("phone_number", phone_number)
    
    async def update_subscription_status(
        self,
        user_id: Union[str, ObjectId],
        status: SubscriptionStatus,
        tier: Optional[SubscriptionTier] = None,
        expires_at: Optional[datetime] = None
    ) -> Optional[User]:
        """
        Update a user's subscription status.
        
        Args:
            user_id: User ID
            status: New subscription status
            tier: Optional new subscription tier
            expires_at: Optional expiration date
            
        Returns:
            Updated user object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        update_data = {"subscription_status": status}
        
        if tier is not None:
            update_data["subscription_tier"] = tier
        
        if expires_at is not None:
            update_data["subscription_expires_at"] = expires_at
        
        return await self.update(user_id, update_data)
    
    async def set_trial_subscription(
        self,
        user_id: Union[str, ObjectId],
        days: int = 14
    ) -> Optional[User]:
        """
        Set a user's subscription to trial status with expiration.
        
        Args:
            user_id: User ID
            days: Number of trial days
            
        Returns:
            Updated user object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        expires_at = datetime.utcnow() + timedelta(days=days)
        
        return await self.update_subscription_status(
            user_id,
            SubscriptionStatus.TRIAL,
            SubscriptionTier.BASIC,
            expires_at
        )
    
    async def update_language_preference(
        self,
        user_id: Union[str, ObjectId],
        language: Language
    ) -> Optional[User]:
        """
        Update a user's language preference.
        
        Args:
            user_id: User ID
            language: New language preference
            
        Returns:
            Updated user object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.update(user_id, {"language": language})
    
    async def update_notification_preference(
        self,
        user_id: Union[str, ObjectId],
        preference: NotificationPreference,
        notification_hours: Optional[Dict[str, int]] = None
    ) -> Optional[User]:
        """
        Update a user's notification preferences.
        
        Args:
            user_id: User ID
            preference: New notification preference
            notification_hours: Optional notification hours
            
        Returns:
            Updated user object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        update_data = {"notification_preference": preference}
        
        if notification_hours is not None:
            update_data["notification_hours"] = notification_hours
        
        return await self.update(user_id, update_data)
    
    async def increment_query_count(
        self,
        user_id: Union[str, ObjectId]
    ) -> Optional[User]:
        """
        Increment a user's query count.
        
        Args:
            user_id: User ID
            
        Returns:
            Updated user object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Convert string ID to ObjectId if needed
            doc_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
            
            # Update the document using $inc operator
            result = await self.collection.update_one(
                {"_id": doc_id},
                {"$inc": {"total_queries": 1}}
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
            logger.error(f"Database error in {self.collection_name}.increment_query_count: {e}")
            raise DatabaseError(f"Failed to increment query count: {e}")
    
    async def increment_cases_tracked_count(
        self,
        user_id: Union[str, ObjectId]
    ) -> Optional[User]:
        """
        Increment a user's cases tracked count.
        
        Args:
            user_id: User ID
            
        Returns:
            Updated user object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Convert string ID to ObjectId if needed
            doc_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
            
            # Update the document using $inc operator
            result = await self.collection.update_one(
                {"_id": doc_id},
                {"$inc": {"total_cases_tracked": 1}}
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
            logger.error(f"Database error in {self.collection_name}.increment_cases_tracked_count: {e}")
            raise DatabaseError(f"Failed to increment cases tracked count: {e}")
    
    async def update_last_active(
        self,
        user_id: Union[str, ObjectId]
    ) -> Optional[User]:
        """
        Update a user's last active timestamp.
        
        Args:
            user_id: User ID
            
        Returns:
            Updated user object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.update(
            user_id,
            {"last_active": datetime.utcnow()}
        )
    
    async def verify_user(
        self,
        user_id: Union[str, ObjectId],
        oab_number: Optional[str] = None
    ) -> Optional[User]:
        """
        Mark a user as verified.
        
        Args:
            user_id: User ID
            oab_number: Optional OAB registration number
            
        Returns:
            Updated user object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        update_data = {"is_verified": True}
        
        if oab_number is not None:
            update_data["oab_number"] = oab_number
        
        return await self.update(user_id, update_data)
    
    async def get_active_users(self) -> List[User]:
        """
        Get all active users (with active or trial subscription).
        
        Returns:
            List of active user objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={
                "subscription_status": {
                    "$in": [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]
                }
            }
        )
    
    async def get_users_with_expired_trial(self) -> List[User]:
        """
        Get users with expired trial subscriptions.
        
        Returns:
            List of users with expired trial subscriptions
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={
                "subscription_status": SubscriptionStatus.TRIAL,
                "subscription_expires_at": {"$lt": datetime.utcnow()}
            }
        )
    
    async def set_whitelist_status(
        self,
        user_id: Union[str, ObjectId],
        is_whitelisted: bool
    ) -> Optional[User]:
        """
        Set a user's whitelist status.
        
        Args:
            user_id: User ID
            is_whitelisted: Whether the user should be whitelisted
            
        Returns:
            Updated user object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.update(
            user_id,
            {"is_whitelisted": is_whitelisted}
        )
    
    async def update_usage_limits(
        self,
        user_id: Union[str, ObjectId],
        max_cases: Optional[int] = None,
        max_notifications_per_day: Optional[int] = None
    ) -> Optional[User]:
        """
        Update a user's usage limits.
        
        Args:
            user_id: User ID
            max_cases: Maximum number of cases the user can track
            max_notifications_per_day: Maximum number of notifications per day
            
        Returns:
            Updated user object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        update_data = {}
        
        if max_cases is not None:
            update_data["max_cases"] = max_cases
        
        if max_notifications_per_day is not None:
            update_data["max_notifications_per_day"] = max_notifications_per_day
        
        return await self.update(user_id, update_data)
