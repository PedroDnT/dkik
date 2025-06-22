"""
Notification database operations for the DKIK WhatsApp Bot.

This module provides a NotificationDB class that extends BaseDB to handle
notification-specific database operations such as finding notifications by user ID,
managing notification statuses, and processing notification queues.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from bson import ObjectId
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.database.base import BaseDB, DatabaseError, DocumentNotFoundError, DuplicateDocumentError
from app.models.notification import Notification, NotificationType, DeliveryStatus, NotificationPriority

# Configure logger
logger = logging.getLogger(__name__)


class NotificationDB(BaseDB[Notification, Notification, Notification]):
    """
    Notification database operations class.
    
    This class extends BaseDB to provide notification-specific database operations
    such as finding notifications by user ID, managing notification statuses,
    and processing notification queues.
    """
    
    async def get_by_user_id(
        self,
        user_id: str,
        limit: int = 20,
        skip: int = 0,
        sort_direction: int = -1  # -1 for descending (newest first)
    ) -> List[Notification]:
        """
        Get notifications for a specific user.
        
        Args:
            user_id: User ID
            limit: Maximum number of notifications to return
            skip: Number of notifications to skip (for pagination)
            sort_direction: Sort direction (1 for ascending, -1 for descending)
            
        Returns:
            List of notification objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={"user_id": user_id},
            sort=[("created_at", sort_direction)],
            skip=skip,
            limit=limit
        )
    
    async def get_by_phone_number(
        self,
        phone_number: str,
        limit: int = 20,
        skip: int = 0
    ) -> List[Notification]:
        """
        Get notifications for a specific phone number.
        
        Args:
            phone_number: WhatsApp phone number
            limit: Maximum number of notifications to return
            skip: Number of notifications to skip (for pagination)
            
        Returns:
            List of notification objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={"phone_number": phone_number},
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit
        )
    
    async def get_by_process_cnj(
        self,
        process_cnj: str,
        limit: int = 20,
        skip: int = 0
    ) -> List[Notification]:
        """
        Get notifications for a specific process.
        
        Args:
            process_cnj: CNJ formatted process number
            limit: Maximum number of notifications to return
            skip: Number of notifications to skip (for pagination)
            
        Returns:
            List of notification objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={"process_cnj": process_cnj},
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit
        )
    
    async def get_by_status(
        self,
        status: DeliveryStatus,
        limit: int = 50,
        skip: int = 0
    ) -> List[Notification]:
        """
        Get notifications with a specific delivery status.
        
        Args:
            status: Delivery status to filter by
            limit: Maximum number of notifications to return
            skip: Number of notifications to skip (for pagination)
            
        Returns:
            List of notification objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={"delivery_status": status},
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit
        )
    
    async def get_by_type(
        self,
        notification_type: NotificationType,
        limit: int = 50,
        skip: int = 0
    ) -> List[Notification]:
        """
        Get notifications of a specific type.
        
        Args:
            notification_type: Type of notification to filter by
            limit: Maximum number of notifications to return
            skip: Number of notifications to skip (for pagination)
            
        Returns:
            List of notification objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={"type": notification_type},
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit
        )
    
    async def update_delivery_status(
        self,
        notification_id: Union[str, ObjectId],
        status: DeliveryStatus,
        error_message: Optional[str] = None
    ) -> Optional[Notification]:
        """
        Update a notification's delivery status.
        
        Args:
            notification_id: Notification ID
            status: New delivery status
            error_message: Optional error message if delivery failed
            
        Returns:
            Updated notification object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        update_data = {"delivery_status": status}
        
        # Add timestamp based on status
        if status == DeliveryStatus.SENT:
            update_data["sent_at"] = datetime.utcnow()
        elif status == DeliveryStatus.DELIVERED:
            update_data["delivered_at"] = datetime.utcnow()
        elif status == DeliveryStatus.READ:
            update_data["read_at"] = datetime.utcnow()
        
        # Add error message if provided
        if error_message is not None:
            update_data["error_message"] = error_message
        
        return await self.update(notification_id, update_data)
    
    async def mark_as_delivered(
        self,
        twilio_sid: str
    ) -> Optional[Notification]:
        """
        Mark a notification as delivered by Twilio SID.
        
        Args:
            twilio_sid: Twilio message SID
            
        Returns:
            Updated notification object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Find the notification by Twilio SID
            notification = await self.get_by_field("twilio_sid", twilio_sid)
            if not notification:
                return None
            
            # Update the notification
            return await self.update(
                str(notification.id),
                {
                    "delivery_status": DeliveryStatus.DELIVERED,
                    "delivered_at": datetime.utcnow()
                }
            )
            
        except DatabaseError as e:
            logger.error(f"Error marking notification as delivered: {e}")
            raise
    
    async def mark_as_read(
        self,
        twilio_sid: str
    ) -> Optional[Notification]:
        """
        Mark a notification as read by Twilio SID.
        
        Args:
            twilio_sid: Twilio message SID
            
        Returns:
            Updated notification object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Find the notification by Twilio SID
            notification = await self.get_by_field("twilio_sid", twilio_sid)
            if not notification:
                return None
            
            # Update the notification
            return await self.update(
                str(notification.id),
                {
                    "delivery_status": DeliveryStatus.READ,
                    "read_at": datetime.utcnow()
                }
            )
            
        except DatabaseError as e:
            logger.error(f"Error marking notification as read: {e}")
            raise
    
    async def record_user_response(
        self,
        notification_id: Union[str, ObjectId],
        response: str
    ) -> Optional[Notification]:
        """
        Record a user's response to a notification.
        
        Args:
            notification_id: Notification ID
            response: User's response text
            
        Returns:
            Updated notification object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.update(
            notification_id,
            {
                "user_response": response,
                "response_received_at": datetime.utcnow()
            }
        )
    
    async def get_queued_notifications(
        self,
        limit: int = 50,
        max_attempts: int = 3
    ) -> List[Notification]:
        """
        Get queued notifications ready to be sent.
        
        Args:
            limit: Maximum number of notifications to return
            max_attempts: Maximum number of delivery attempts
            
        Returns:
            List of queued notification objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        now = datetime.utcnow()
        
        return await self.get_all(
            filter_query={
                "delivery_status": DeliveryStatus.QUEUED,
                "delivery_attempts": {"$lt": max_attempts},
                "$or": [
                    {"scheduled_for": None},
                    {"scheduled_for": {"$lte": now}}
                ]
            },
            sort=[("priority", -1), ("created_at", 1)],
            limit=limit
        )
    
    async def get_failed_notifications(
        self,
        limit: int = 50,
        since: Optional[datetime] = None
    ) -> List[Notification]:
        """
        Get failed notifications.
        
        Args:
            limit: Maximum number of notifications to return
            since: Optional datetime to filter notifications since
            
        Returns:
            List of failed notification objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        filter_query = {"delivery_status": DeliveryStatus.FAILED}
        
        if since:
            filter_query["created_at"] = {"$gte": since}
        
        return await self.get_all(
            filter_query=filter_query,
            sort=[("created_at", -1)],
            limit=limit
        )
    
    async def retry_failed_notifications(
        self,
        max_age_hours: int = 24
    ) -> int:
        """
        Reset failed notifications to queued status for retry.
        
        Args:
            max_age_hours: Maximum age in hours for notifications to retry
            
        Returns:
            Number of notifications reset for retry
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            
            # Update all eligible failed notifications
            result = await self.collection.update_many(
                {
                    "delivery_status": DeliveryStatus.FAILED,
                    "created_at": {"$gte": cutoff_time},
                    "delivery_attempts": {"$lt": 3}
                },
                {
                    "$set": {
                        "delivery_status": DeliveryStatus.QUEUED,
                        "error_message": None,
                        "last_attempt_at": None
                    }
                }
            )
            
            # Return number of documents updated
            return result.modified_count
            
        except PyMongoError as e:
            logger.error(f"Database error in {self.collection_name}.retry_failed_notifications: {e}")
            raise DatabaseError(f"Failed to retry failed notifications: {e}")
    
    async def increment_delivery_attempt(
        self,
        notification_id: Union[str, ObjectId]
    ) -> Optional[Notification]:
        """
        Increment a notification's delivery attempt counter.
        
        Args:
            notification_id: Notification ID
            
        Returns:
            Updated notification object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        try:
            # Convert string ID to ObjectId if needed
            doc_id = ObjectId(notification_id) if isinstance(notification_id, str) else notification_id
            
            # Update the document
            result = await self.collection.update_one(
                {"_id": doc_id},
                {
                    "$inc": {"delivery_attempts": 1},
                    "$set": {"last_attempt_at": datetime.utcnow()}
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
            logger.error(f"Database error in {self.collection_name}.increment_delivery_attempt: {e}")
            raise DatabaseError(f"Failed to increment delivery attempt: {e}")
    
    async def schedule_notification(
        self,
        notification_id: Union[str, ObjectId],
        scheduled_for: datetime
    ) -> Optional[Notification]:
        """
        Schedule a notification for future delivery.
        
        Args:
            notification_id: Notification ID
            scheduled_for: When to send the notification
            
        Returns:
            Updated notification object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.update(
            notification_id,
            {"scheduled_for": scheduled_for}
        )
    
    async def update_priority(
        self,
        notification_id: Union[str, ObjectId],
        priority: NotificationPriority
    ) -> Optional[Notification]:
        """
        Update a notification's priority.
        
        Args:
            notification_id: Notification ID
            priority: New priority level
            
        Returns:
            Updated notification object or None if not found
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.update(notification_id, {"priority": priority})
    
    async def count_notifications_by_user_today(self, user_id: str) -> int:
        """
        Count the number of notifications sent to a user today.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of notifications
            
        Raises:
            DatabaseError: If any database error occurs
        """
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        return await self.count(
            filter_query={
                "user_id": user_id,
                "created_at": {"$gte": today_start}
            }
        )
    
    async def get_notifications_by_group(
        self,
        notification_group_id: str,
        limit: int = 50
    ) -> List[Notification]:
        """
        Get notifications by group ID.
        
        Args:
            notification_group_id: Group ID for related notifications
            limit: Maximum number of notifications to return
            
        Returns:
            List of notification objects
            
        Raises:
            DatabaseError: If any database error occurs
        """
        return await self.get_all(
            filter_query={"notification_group_id": notification_group_id},
            sort=[("created_at", -1)],
            limit=limit
        )
    
    async def delete_old_notifications(
        self,
        days: int = 30
    ) -> int:
        """
        Delete notifications older than the specified number of days.
        
        Args:
            days: Number of days to keep notifications
            
        Returns:
            Number of notifications deleted
            
        Raises:
            DatabaseError: If any database error occurs
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        return await self.bulk_delete(
            filter_query={"created_at": {"$lt": cutoff_date}}
        )
