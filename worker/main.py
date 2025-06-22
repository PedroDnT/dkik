"""
Main entry point for the DKIK WhatsApp Bot background worker.

This module sets up and runs the background worker that handles periodic tasks
such as checking for case updates, sending notifications, and managing scheduled
reminders for court hearings.

The worker runs as a separate process from the main FastAPI application
and uses APScheduler for task scheduling.
"""
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import uvloop
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

# Add parent directory to path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.database import connect_to_mongo, close_mongo_connection, get_database
from app.database.users import UserDB
from app.database.processes import ProcessDB
from app.database.subscriptions import SubscriptionDB
from app.database.process_movements import ProcessMovementDB
from app.database.notifications import NotificationDB
from app.models.user import User
from app.models.process import Process
from app.models.subscription import Subscription
from app.models.process_movement import ProcessMovement
from app.models.notification import Notification, NotificationType, DeliveryStatus
from app.tools.datajud_tool import DataJudTool

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("dkik.worker")

# Load environment variables
load_dotenv()

# Global scheduler
scheduler = AsyncIOScheduler()


async def check_process_updates():
    """
    Check for updates on tracked processes.
    
    This task:
    1. Retrieves all tracked processes from the database
    2. Checks for new movements using the DataJud API
    3. Creates new movement records if found
    4. Sends notifications to subscribed users
    """
    try:
        logger.info("Running task: check_process_updates")
        
        # Get database instance
        db = await get_database()
        
        # Initialize database operations
        process_db = ProcessDB(db, "processes", Process)
        movement_db = ProcessMovementDB(db, "process_movements", ProcessMovement)
        subscription_db = SubscriptionDB(db, "subscriptions", Subscription)
        
        # Get all tracked processes
        tracked_processes = await process_db.get_tracked_processes()
        logger.info(f"Found {len(tracked_processes)} tracked processes")
        
        # Initialize DataJud tool
        datajud_tool = DataJudTool()
        
        # Check each process for updates
        for process in tracked_processes:
            try:
                # Get the latest movements from DataJud API
                query = {
                    "operation": "get_process_movements",
                    "cnj_number": process.cnj_number,
                    "limit": 10
                }
                result_json = await datajud_tool._arun(json.dumps(query))
                result = json.loads(result_json)
                
                if "error" in result:
                    logger.error(f"Error checking process {process.cnj_number}: {result['error']}")
                    continue
                
                # Get movements from the result
                movements = result.get("movements", [])
                if not movements:
                    logger.info(f"No movements found for process {process.cnj_number}")
                    continue
                
                # Get the latest movement
                latest_movement = movements[0]
                latest_movement_id = latest_movement.get("id")
                
                # Check if this is a new movement
                if latest_movement_id != process.last_movement_id:
                    logger.info(f"New movement found for process {process.cnj_number}")
                    
                    # Update process with latest movement
                    movement_date = datetime.fromisoformat(latest_movement.get("date").replace("Z", "+00:00"))
                    await process_db.update_last_movement(
                        process.cnj_number,
                        movement_date,
                        latest_movement.get("description", ""),
                        latest_movement_id
                    )
                    
                    # Create new movement record
                    new_movement = {
                        "process_cnj": process.cnj_number,
                        "movement_id": latest_movement_id,
                        "date": movement_date,
                        "description": latest_movement.get("description", ""),
                        "type": latest_movement.get("type", "OTHER"),
                        "datajud_metadata": latest_movement
                    }
                    await movement_db.create(new_movement)
                    
                    # Get all subscriptions for this process
                    subscriptions = await subscription_db.get_by_process_cnj(process.cnj_number)
                    
                    # Send notifications to subscribers
                    for subscription in subscriptions:
                        if subscription.is_active:
                            await send_movement_notification(
                                subscription.user_id,
                                process.cnj_number,
                                latest_movement_id,
                                latest_movement.get("description", ""),
                                str(subscription.id)
                            )
                
                # Mark process as checked
                await process_db.mark_as_checked(process.cnj_number)
                
            except Exception as e:
                logger.exception(f"Error processing updates for {process.cnj_number}: {e}")
        
        logger.info("Completed task: check_process_updates")
        
    except Exception as e:
        logger.exception(f"Error in check_process_updates task: {e}")


async def send_hearing_reminders():
    """
    Send reminders for upcoming court hearings.
    
    This task:
    1. Finds processes with hearings scheduled in the next 24 hours
    2. Sends reminders to subscribed users
    """
    try:
        logger.info("Running task: send_hearing_reminders")
        
        # Get database instance
        db = await get_database()
        
        # Initialize database operations
        process_db = ProcessDB(db, "processes", Process)
        subscription_db = SubscriptionDB(db, "subscriptions", Subscription)
        
        # Get date range for tomorrow's hearings
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=1)
        
        # Get processes with hearings in the next 24 hours
        processes = await process_db.get_processes_with_hearings(start_date, end_date)
        logger.info(f"Found {len(processes)} processes with upcoming hearings")
        
        # Send reminders for each process
        for process in processes:
            try:
                # Filter hearings for the next 24 hours
                upcoming_hearings = [
                    h for h in process.hearings 
                    if start_date <= h["date"] <= end_date
                ]
                
                if not upcoming_hearings:
                    continue
                
                # Get all subscriptions for this process
                subscriptions = await subscription_db.get_by_process_cnj(process.cnj_number)
                
                # Send notifications to subscribers
                for subscription in subscriptions:
                    if subscription.is_active:
                        for hearing in upcoming_hearings:
                            await send_hearing_notification(
                                subscription.user_id,
                                process.cnj_number,
                                hearing,
                                str(subscription.id)
                            )
                
            except Exception as e:
                logger.exception(f"Error sending hearing reminders for {process.cnj_number}: {e}")
        
        logger.info("Completed task: send_hearing_reminders")
        
    except Exception as e:
        logger.exception(f"Error in send_hearing_reminders task: {e}")


async def clean_expired_subscriptions():
    """
    Clean up expired subscriptions and trial periods.
    
    This task:
    1. Finds users with expired trial subscriptions
    2. Updates their subscription status to expired
    3. Sends notifications about expiration
    """
    try:
        logger.info("Running task: clean_expired_subscriptions")
        
        # Get database instance
        db = await get_database()
        
        # Initialize database operations
        user_db = UserDB(db, "users", User)
        
        # Get users with expired trial subscriptions
        expired_users = await user_db.get_users_with_expired_trial()
        logger.info(f"Found {len(expired_users)} users with expired trial subscriptions")
        
        # Update each user's subscription status
        for user in expired_users:
            try:
                # Update subscription status to expired
                await user_db.update_subscription_status(
                    str(user.id),
                    SubscriptionStatus.EXPIRED
                )
                
                # Send expiration notification
                await send_subscription_notification(
                    str(user.id),
                    user.phone_number,
                    "Período de teste expirado",
                    (
                        "Seu período de teste do DKIK expirou. "
                        "Para continuar utilizando o serviço, por favor, "
                        "entre em contato conosco para adquirir uma assinatura."
                    )
                )
                
            except Exception as e:
                logger.exception(f"Error processing expired subscription for user {user.id}: {e}")
        
        logger.info("Completed task: clean_expired_subscriptions")
        
    except Exception as e:
        logger.exception(f"Error in clean_expired_subscriptions task: {e}")


async def process_notification_queue():
    """
    Process the notification queue.
    
    This task:
    1. Finds queued notifications
    2. Attempts to send them via Twilio
    3. Updates their status based on the result
    """
    try:
        logger.info("Running task: process_notification_queue")
        
        # Get database instance
        db = await get_database()
        
        # Initialize database operations
        notification_db = NotificationDB(db, "notifications", Notification)
        
        # Get queued notifications
        queued_notifications = await notification_db.get_queued_notifications(limit=50)
        logger.info(f"Found {len(queued_notifications)} queued notifications")
        
        # Process each notification
        for notification in queued_notifications:
            try:
                # Get the notification details
                phone_number = notification.phone_number
                message = notification.message
                media_urls = notification.media_urls
                
                # Import Twilio client here to avoid circular imports
                from app.main import twilio_client
                
                # Prepare message parameters
                message_params = {
                    "from_": settings.TWILIO_WHATSAPP_NUMBER,
                    "body": message,
                    "to": f"whatsapp:{phone_number}"
                }
                
                # Add media if provided
                if media_urls:
                    message_params["media_url"] = media_urls
                
                # Send the message
                twilio_message = twilio_client.messages.create(**message_params)
                
                # Update notification status
                await notification_db.update(
                    str(notification.id),
                    {
                        "twilio_sid": twilio_message.sid,
                        "delivery_status": DeliveryStatus.SENT,
                        "sent_at": datetime.utcnow(),
                        "delivery_attempts": notification.delivery_attempts + 1
                    }
                )
                
                logger.info(f"Sent notification {notification.id} to {phone_number}")
                
            except Exception as e:
                logger.exception(f"Error sending notification {notification.id}: {e}")
                
                # Update notification with error
                await notification_db.update(
                    str(notification.id),
                    {
                        "delivery_status": DeliveryStatus.FAILED,
                        "error_message": str(e),
                        "delivery_attempts": notification.delivery_attempts + 1
                    }
                )
        
        logger.info("Completed task: process_notification_queue")
        
    except Exception as e:
        logger.exception(f"Error in process_notification_queue task: {e}")


async def send_movement_notification(
    user_id: str,
    process_cnj: str,
    movement_id: str,
    movement_description: str,
    subscription_id: str
):
    """
    Send a notification about a new process movement.
    
    Args:
        user_id: User ID
        process_cnj: CNJ number of the process
        movement_id: ID of the movement
        movement_description: Description of the movement
        subscription_id: ID of the subscription
    """
    try:
        # Get database instance
        db = await get_database()
        
        # Initialize database operations
        user_db = UserDB(db, "users", User)
        notification_db = NotificationDB(db, "notifications", Notification)
        
        # Get the user
        user = await user_db.get(user_id)
        if not user:
            logger.error(f"User {user_id} not found")
            return
        
        # Create notification
        notification_data = {
            "user_id": user_id,
            "phone_number": user.phone_number,
            "process_cnj": process_cnj,
            "movement_id": movement_id,
            "subscription_id": subscription_id,
            "type": NotificationType.MOVEMENT,
            "title": "Nova Movimentação",
            "message": f"Processo {process_cnj} teve nova movimentação: {movement_description}",
            "delivery_status": DeliveryStatus.QUEUED
        }
        
        await notification_db.create(notification_data)
        logger.info(f"Created movement notification for user {user_id}, process {process_cnj}")
        
    except Exception as e:
        logger.exception(f"Error creating movement notification: {e}")


async def send_hearing_notification(
    user_id: str,
    process_cnj: str,
    hearing: Dict,
    subscription_id: str
):
    """
    Send a notification about an upcoming hearing.
    
    Args:
        user_id: User ID
        process_cnj: CNJ number of the process
        hearing: Hearing data
        subscription_id: ID of the subscription
    """
    try:
        # Get database instance
        db = await get_database()
        
        # Initialize database operations
        user_db = UserDB(db, "users", User)
        notification_db = NotificationDB(db, "notifications", Notification)
        
        # Get the user
        user = await user_db.get(user_id)
        if not user:
            logger.error(f"User {user_id} not found")
            return
        
        # Format hearing date and time
        hearing_date = hearing.get("date")
        hearing_time = hearing.get("time", "")
        hearing_type = hearing.get("type", "")
        hearing_location = hearing.get("location", "")
        
        # Format date for display
        formatted_date = hearing_date.strftime("%d/%m/%Y")
        
        # Create notification
        notification_data = {
            "user_id": user_id,
            "phone_number": user.phone_number,
            "process_cnj": process_cnj,
            "subscription_id": subscription_id,
            "type": NotificationType.HEARING,
            "title": "Lembrete de Audiência",
            "message": (
                f"Lembrete: Audiência para o processo {process_cnj} "
                f"agendada para {formatted_date} às {hearing_time}.\n"
                f"Tipo: {hearing_type}\n"
                f"Local: {hearing_location}"
            ),
            "delivery_status": DeliveryStatus.QUEUED
        }
        
        await notification_db.create(notification_data)
        logger.info(f"Created hearing notification for user {user_id}, process {process_cnj}")
        
    except Exception as e:
        logger.exception(f"Error creating hearing notification: {e}")


async def send_subscription_notification(
    user_id: str,
    phone_number: str,
    title: str,
    message: str
):
    """
    Send a notification about subscription status.
    
    Args:
        user_id: User ID
        phone_number: User's phone number
        title: Notification title
        message: Notification message
    """
    try:
        # Get database instance
        db = await get_database()
        
        # Initialize database operations
        notification_db = NotificationDB(db, "notifications", Notification)
        
        # Create notification
        notification_data = {
            "user_id": user_id,
            "phone_number": phone_number,
            "type": NotificationType.SUBSCRIPTION,
            "title": title,
            "message": message,
            "delivery_status": DeliveryStatus.QUEUED
        }
        
        await notification_db.create(notification_data)
        logger.info(f"Created subscription notification for user {user_id}")
        
    except Exception as e:
        logger.exception(f"Error creating subscription notification: {e}")


def setup_scheduler():
    """
    Set up the task scheduler with all periodic tasks.
    
    This function configures the APScheduler with all the tasks
    that need to run periodically in the background.
    """
    logger.info("Setting up scheduler...")
    
    # Check for process updates every X minutes
    scheduler.add_job(
        check_process_updates,
        IntervalTrigger(minutes=settings.WORKER_POLLING_INTERVAL_MINUTES),
        id="check_process_updates",
        name="Check for process updates",
        replace_existing=True
    )
    
    # Send hearing reminders at 8:00 AM every day
    scheduler.add_job(
        send_hearing_reminders,
        CronTrigger(hour=8, minute=0),
        id="send_hearing_reminders",
        name="Send hearing reminders",
        replace_existing=True
    )
    
    # Clean expired subscriptions at midnight every day
    scheduler.add_job(
        clean_expired_subscriptions,
        CronTrigger(hour=0, minute=0),
        id="clean_expired_subscriptions",
        name="Clean expired subscriptions",
        replace_existing=True
    )
    
    # Process notification queue every 5 minutes
    scheduler.add_job(
        process_notification_queue,
        IntervalTrigger(minutes=5),
        id="process_notification_queue",
        name="Process notification queue",
        replace_existing=True
    )
    
    logger.info("Scheduler setup complete")


def handle_signals():
    """
    Set up signal handlers for graceful shutdown.
    
    This function configures handlers for SIGINT and SIGTERM
    to ensure the worker shuts down gracefully.
    """
    def shutdown_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        scheduler.shutdown()
        
        # Run the event loop to close the MongoDB connection
        loop = asyncio.get_event_loop()
        loop.run_until_complete(close_mongo_connection())
        
        logger.info("Shutdown complete")
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    logger.info("Signal handlers registered")


async def startup():
    """
    Perform startup tasks.
    
    This function connects to MongoDB and sets up the scheduler.
    """
    logger.info("Starting DKIK WhatsApp Bot worker...")
    
    # Connect to MongoDB
    await connect_to_mongo()
    
    # Set up scheduler
    setup_scheduler()
    
    # Start scheduler
    scheduler.start()
    
    logger.info("DKIK WhatsApp Bot worker started successfully")


async def main():
    """
    Main entry point for the worker.
    
    This function sets up signal handlers, performs startup tasks,
    and keeps the worker running.
    """
    # Set up signal handlers
    handle_signals()
    
    # Perform startup tasks
    await startup()
    
    # Keep the worker running
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    # Use uvloop for better performance
    uvloop.install()
    
    # Run the main function
    asyncio.run(main())
