"""
Agents package initialization.

This module imports and exposes the agent factory functionality,
making it easily accessible throughout the application.
"""
from app.agents.agent_factory import create_agent

__all__ = ["create_agent"]
