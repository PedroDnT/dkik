"""
Main FastAPI application for the DKIK WhatsApp Bot.

This module sets up the FastAPI application, configures middleware,
defines API routes, and implements the Twilio webhook for WhatsApp integration.
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain.agents import AgentExecutor
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client

from app.config import settings
from app.database import close_mongo_connection, connect_to_mongo, get_database
from app.database.users import UserDB
from app.database.processes import ProcessDB
from app.database.subscriptions import SubscriptionDB
from app.database.process_movements import ProcessMovementDB
from app.database.notifications import NotificationDB
from app.models.user import User, SubscriptionStatus
from app.models.notification import Notification, NotificationType, DeliveryStatus
from app.agents.agent_factory import create_agent
from app.tools import get_tools

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create Twilio client
twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


# Startup and shutdown events
@app.on_event("startup")
async def startup_db_client():
    """
    Connect to MongoDB on application startup.
    """
    logger.info("Starting up DKIK WhatsApp Bot...")
    await connect_to_mongo()
    logger.info("DKIK WhatsApp Bot started successfully")


@app.on_event("shutdown")
async def shutdown_db_client():
    """
    Close MongoDB connection on application shutdown.
    """
    logger.info("Shutting down DKIK WhatsApp Bot...")
    await close_mongo_connection()
    logger.info("DKIK WhatsApp Bot shut down successfully")


# Models for API requests and responses
class WhatsAppMessage(BaseModel):
    """
    Model for incoming WhatsApp messages from Twilio.
    """
    From: str = Field(..., description="Sender's WhatsApp number")
    Body: str = Field(..., description="Message content")
    ProfileName: Optional[str] = Field(None, description="Sender's profile name")
    WaId: Optional[str] = Field(None, description="WhatsApp ID")
    SmsMessageSid: Optional[str] = Field(None, description="Message SID")


class APIResponse(BaseModel):
    """
    Standard API response model.
    """
    success: bool = Field(..., description="Whether the request was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")


# Dependency to validate Twilio requests
async def validate_twilio_request(request: Request) -> bool:
    """
    Validate that the request is coming from Twilio.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        True if the request is valid, False otherwise
        
    Raises:
        HTTPException: If the request is invalid
    """
    # Get the Twilio signature from the request headers
    twilio_signature = request.headers.get("X-Twilio-Signature")
    if not twilio_signature:
        logger.warning("Missing X-Twilio-Signature header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Twilio-Signature header",
        )
    
    # Get the request URL and form data
    url = str(request.url)
    form_data = await request.form()
    form_dict = dict(form_data)
    
    # Validate the request
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    is_valid = validator.validate(url, form_dict, twilio_signature)
    
    if not is_valid:
        logger.warning("Invalid Twilio signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Twilio signature",
        )
    
    return True


# Helper function to get or create a user
async def get_or_create_user(phone_number: str, profile_name: Optional[str] = None) -> User:
    """
    Get an existing user or create a new one if not found.
    
    Args:
        phone_number: User's WhatsApp phone number
        profile_name: User's WhatsApp profile name
        
    Returns:
        User object
    """
    db = await get_database()
    user_db = UserDB(db, "users", User)
    
    # Try to get the user
    user = await user_db.get_by_field("phone_number", phone_number)
    
    # If user doesn't exist, create a new one
    if not user:
        logger.info(f"Creating new user with phone number {phone_number}")
        user_data = {
            "phone_number": phone_number,
            "name": profile_name,
            "subscription_status": SubscriptionStatus.TRIAL,
            "is_whitelisted": phone_number in settings.ALLOWED_PHONE_NUMBERS,
        }
        user = await user_db.create(user_data)
        
        # Send welcome message
        await send_notification(
            user_id=str(user.id),
            phone_number=phone_number,
            title="Bem-vindo ao DKIK",
            message=(
                "Olá! Bem-vindo ao DKIK, seu assistente jurídico para acompanhamento "
                "de processos no TJSP. Você pode consultar o status de processos, "
                "receber notificações sobre movimentações e muito mais.\n\n"
                "Para começar, envie o número de um processo no formato CNJ "
                "(NNNNNNN-DD.YYYY.J.TR.OOOO) ou faça uma pergunta em linguagem natural."
            ),
            notification_type=NotificationType.WELCOME,
        )
    else:
        # Update last active timestamp
        await user_db.update(
            str(user.id),
            {"last_active": datetime.utcnow()}
        )
    
    return user


# Helper function to send a notification
async def send_notification(
    user_id: str,
    phone_number: str,
    title: str,
    message: str,
    notification_type: NotificationType = NotificationType.SYSTEM,
    process_cnj: Optional[str] = None,
    movement_id: Optional[str] = None,
    subscription_id: Optional[str] = None,
    media_urls: List[str] = None,
) -> Notification:
    """
    Send a notification to a user via WhatsApp.
    
    Args:
        user_id: User ID
        phone_number: User's WhatsApp phone number
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        process_cnj: Optional CNJ number of related process
        movement_id: Optional ID of related movement
        subscription_id: Optional ID of related subscription
        media_urls: Optional list of media URLs
        
    Returns:
        Created Notification object
    """
    db = await get_database()
    notification_db = NotificationDB(db, "notifications", Notification)
    
    # Create notification record
    notification_data = {
        "user_id": user_id,
        "phone_number": phone_number,
        "type": notification_type,
        "title": title,
        "message": message,
        "process_cnj": process_cnj,
        "movement_id": movement_id,
        "subscription_id": subscription_id,
        "media_urls": media_urls or [],
        "delivery_status": DeliveryStatus.QUEUED,
    }
    notification = await notification_db.create(notification_data)
    
    try:
        # Send WhatsApp message via Twilio
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
        
        # Update notification with Twilio SID and status
        await notification_db.update(
            str(notification.id),
            {
                "twilio_sid": twilio_message.sid,
                "delivery_status": DeliveryStatus.SENT,
                "sent_at": datetime.utcnow(),
            }
        )
        
        logger.info(f"Notification sent to {phone_number}: {title}")
        
    except Exception as e:
        logger.error(f"Failed to send notification to {phone_number}: {e}")
        
        # Update notification with error
        await notification_db.update(
            str(notification.id),
            {
                "delivery_status": DeliveryStatus.FAILED,
                "error_message": str(e),
            }
        )
    
    return notification


# API routes
@app.get("/", include_in_schema=False)
async def root():
    """
    Root endpoint that redirects to the API documentation.
    """
    return {"message": "DKIK WhatsApp Bot API", "docs": "/api/docs"}


@app.get("/api/health", response_model=APIResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint to verify the API is running.
    """
    return {
        "success": True,
        "message": "DKIK WhatsApp Bot API is running",
        "data": {
            "version": settings.PROJECT_VERSION,
            "timestamp": datetime.utcnow().isoformat(),
        }
    }


@app.post("/webhook", tags=["Webhook"])
async def twilio_webhook(
    request: Request,
    valid_request: bool = Depends(validate_twilio_request)
):
    """
    Webhook endpoint for Twilio WhatsApp messages.
    
    This endpoint receives incoming WhatsApp messages from Twilio,
    processes them with the LangChain agent, and sends responses back.
    
    Args:
        request: FastAPI Request object
        valid_request: Whether the request is valid (from dependency)
        
    Returns:
        TwiML response
    """
    try:
        # Parse the form data
        form_data = await request.form()
        
        # Extract message details
        from_number = form_data.get("From", "").replace("whatsapp:", "")
        body = form_data.get("Body", "")
        profile_name = form_data.get("ProfileName")
        
        logger.info(f"Received message from {from_number}: {body}")
        
        # Get or create the user
        user = await get_or_create_user(from_number, profile_name)
        
        # Process the message with the LangChain agent
        response_text = await process_message(user, body)
        
        # Create TwiML response
        twiml_response = MessagingResponse()
        twiml_response.message(response_text)
        
        # Log the interaction
        logger.info(f"Sent response to {from_number}")
        
        # Return TwiML response
        return Response(
            content=str(twiml_response),
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.exception(f"Error processing webhook: {e}")
        
        # Create error response
        twiml_response = MessagingResponse()
        twiml_response.message(
            "Desculpe, ocorreu um erro ao processar sua mensagem. "
            "Por favor, tente novamente mais tarde."
        )
        
        return Response(
            content=str(twiml_response),
            media_type="application/xml",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


async def process_message(user: User, message: str) -> str:
    """
    Process a message with the LangChain agent.
    
    Args:
        user: User object
        message: Message content
        
    Returns:
        Response text
    """
    try:
        # Create tools for the agent
        tools = get_tools(user_id=str(user.id))
        
        # Create the LangChain agent
        agent = create_agent(
            tools=tools,
            user_id=str(user.id),
            user_name=user.name,
            user_language=user.language.value
        )
        
        # Run the agent
        result = await agent.ainvoke({"input": message})
        response = result["output"]
        
        # Update user's total queries
        db = await get_database()
        user_db = UserDB(db, "users", User)
        await user_db.update(
            str(user.id),
            {"total_queries": user.total_queries + 1}
        )
        
        return response
        
    except Exception as e:
        logger.exception(f"Error processing message: {e}")
        return (
            "Desculpe, não consegui processar sua mensagem. "
            "Por favor, tente novamente ou entre em contato com o suporte."
        )


# Run the application
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
