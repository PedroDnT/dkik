"""
Tools package initialization.

This module imports all agent tools to make them easily accessible
for the LangChain agent. Tools are Python functions or classes that
provide specific capabilities to the agent.
"""
from typing import List, Optional

from langchain.tools import BaseTool

# Import all tools
from app.tools.datajud_tool import DataJudTool
from app.tools.subscription_tool import SubscriptionTool
from app.tools.process_tool import ProcessTool
from app.tools.notification_tool import NotificationTool
from app.tools.user_tool import UserTool

__all__ = [
    "DataJudTool",
    "SubscriptionTool",
    "ProcessTool",
    "NotificationTool",
    "UserTool",
    "get_tools",
]


def get_tools(user_id: Optional[str] = None) -> List[BaseTool]:
    """
    Get all tools for the LangChain agent.
    
    This function returns all tools that the agent can use to interact
    with external systems and databases. Some tools may require a user_id
    for personalized operations.
    
    Args:
        user_id: Optional user ID for personalized tools
        
    Returns:
        List of LangChain tools
    """
    tools = [
        DataJudTool(),
        ProcessTool(),
        NotificationTool(),
    ]
    
    # Add user-specific tools if user_id is provided
    if user_id:
        tools.extend([
            SubscriptionTool(user_id=user_id),
            UserTool(user_id=user_id),
        ])
    
    return tools
