"""
LitePolis Router ParticiAPI - ParticiAPI-compatible API Implementation

This module implements the ParticiAPI specification endpoints for the LitePolis system.
It provides a simpler alternative API for the ParticiApp frontend.

ParticiAPI Endpoints:
- POST /api/session - Create/refresh session
- GET /api/conversations/{conversation_id} - Get conversation
- GET /api/conversations/{conversation_id}/results/ - Get results
- POST /api/conversations/{conversation_id}/statements/ - Submit statement
- GET /api/conversations/{conversation_id}/statements/ - Get statements
- GET /api/conversations/{conversation_id}/participant - Get participant info
- PUT /api/conversations/{conversation_id}/participant/notifications - Set notifications
- GET /api/conversations/{conversation_id}/participant/notifications - Get notifications
- PUT /api/conversations/{conversation_id}/votes/{tid} - Submit vote
"""

from .core import router, prefix, dependencies

__all__ = ["router", "prefix", "dependencies"]
