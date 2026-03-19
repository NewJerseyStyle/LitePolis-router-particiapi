"""
LitePolis Router ParticiAPI - ParticiAPI Specification Implementation

This module implements the ParticiAPI specification endpoints for the LitePolis system.
It provides a simpler alternative API for the ParticiApp frontend.

ParticiAPI Spec: https://partici.app/

Key differences from Polis API:
- Simpler endpoint structure (/api/ prefix)
- Session-based authentication with CSRF tokens
- Problem+JSON error responses (RFC 7807)
- Vote values: AGREE=-1, NEUTRAL=0, DISAGREE=1 (inverted from Polis)
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends, Header, Cookie, Response, Request
from fastapi.responses import JSONResponse
from datetime import datetime
import hashlib
import secrets
import uuid
import os

from litepolis_database_particiapi import DatabaseActor
from litepolis_database_particiapi.Actor import (
    ConversationNotFoundError,
    ConversationInactiveError,
    StatementNotFoundError,
    NotificationsNotAvailableError,
    EmailAddressMissingError,
    VotingNotAllowedError,
    StatementsNotAllowedError,
    StatementExistsError,
    ResultsNotAvailableError,
    VoteValue,
    Statement,
    Result,
    GroupResults,
    Results,
    ConversationResponse,
    VoteResponse,
    Notifications,
    Participant,
    MIN_VOTES_COUNT,
)
from litepolis_database_default import DatabaseActor as BaseActor

router = APIRouter()
prefix = __name__.split('.')[-2]
prefix = '_'.join(prefix.split('_')[2:])
dependencies = []

# Configuration defaults
DEFAULT_CONFIG: Dict[str, Any] = {
    "session_secret": "litepolis-particiapi-secret-change-in-production",
    "csrf_token_expire_hours": 24,
}

# Get config with fallback to defaults
try:
    from litepolis import get_config
    session_secret = get_config("litepolis_router_particiapi", "session_secret")
    csrf_token_expire_hours = int(get_config("litepolis_router_particiapi", "csrf_token_expire_hours"))
except (ValueError, Exception):
    # Config actor not available yet, use defaults
    session_secret = DEFAULT_CONFIG["session_secret"]
    csrf_token_expire_hours = DEFAULT_CONFIG["csrf_token_expire_hours"]

# Problem Details Types (RFC 7807)
PROBLEM_TYPES = {
    "authentication_required": "tag:partici.app,2024:api:errors:authentication_required",
    "session_required": "tag:partici.app,2024:api:errors:session_required",
    "not_found": "tag:partici.app,2024:api:errors:not_found",
    "conversation_inactive": "tag:partici.app,2024:api:errors:conversation_inactive",
    "statements_not_allowed": "tag:partici.app,2024:api:errors:statements_not_allowed",
    "statement_exists": "tag:partici.app,2024:api:errors:statement_exists",
    "notifications_not_available": "tag:partici.app,2024:api:errors:notifications_not_available",
    "email_address_missing": "tag:partici.app,2024:api:errors:email_address_missing",
    "results_not_available": "tag:partici.app,2024:api:errors:results_not_available",
    "malformed_request": "tag:partici.app,2024:api:errors:malformed_request",
}


class ProblemDetailResponse(JSONResponse):
    """RFC 7807 Problem Details response."""
    media_type = "application/problem+json"
    
    def __init__(self, status: int, problem_type: str, title: str, detail: str = ""):
        content = {
            "type": problem_type,
            "title": title,
            "status": status,
            "detail": detail,
        }
        super().__init__(status_code=status, content=content, media_type=self.media_type)


def problem_response(status: int, problem_type_key: str, detail: str = ""):
    """Create a Problem Details response."""
    return ProblemDetailResponse(
        status=status,
        problem_type=PROBLEM_TYPES.get(problem_type_key, "about:blank"),
        title=problem_type_key.replace("_", " ").title(),
        detail=detail
    )


# Request/Response Models
class StatementInput(BaseModel):
    text: str = Field(max_length=1000)


class VoteInput(BaseModel):
    value: int  # -1=agree, 0=neutral, 1=disagree


class NotificationsInput(BaseModel):
    enabled: bool = False


# Session Management
def generate_csrf_token() -> str:
    return secrets.token_hex(32)


def get_session(request: Request) -> Dict:
    """Get session data from request state."""
    return getattr(request.state, "session", {})


def have_session(request: Request) -> bool:
    """Check if session exists."""
    return hasattr(request.state, "session") and request.state.session.get("uid") is not None


async def get_current_participant(
    request: Request,
    authorization: Optional[str] = Header(None),
    particiapi_session: Optional[str] = Cookie(None, alias="particiapi_session"),
) -> Optional[Dict]:
    """Get current participant from session or token."""
    session_data = {}
    
    # Check for session cookie
    if particiapi_session:
        # In production, decode and verify session token
        # For now, simple UUID parsing
        try:
            # Session format: "uid:csrf_token"
            parts = particiapi_session.split(":")
            if len(parts) >= 2:
                session_data["uid"] = int(parts[0])
                session_data["csrf_token"] = parts[1]
                session_data["authenticated"] = True
        except (ValueError, TypeError):
            pass
    
    request.state.session = session_data
    return session_data if session_data.get("uid") else None


async def require_session(
    request: Request,
    participant: Optional[Dict] = Depends(get_current_participant)
) -> Dict:
    """Require an active session."""
    if not participant or not participant.get("uid"):
        raise HTTPException(status_code=403, detail={"type": "session_required"})
    return participant


async def require_auth(
    request: Request,
    participant: Optional[Dict] = Depends(get_current_participant)
) -> Dict:
    """Require authentication."""
    if not participant:
        raise HTTPException(status_code=403, detail={"type": "authentication_required"})
    return participant


def check_csrf(request: Request, session: Dict):
    """Check CSRF token for state-changing requests."""
    csrf_header = request.headers.get("X-CSRF-Token", "")
    csrf_token = session.get("csrf_token", "")
    if csrf_header != csrf_token:
        return problem_response(403, "session_required", "Invalid CSRF token")
    return None


# =====================
# Session Endpoint
# =====================

@router.post("/session")
async def create_session(
    request: Request,
    response: Response,
    create: bool = False,
    participant: Optional[Dict] = Depends(get_current_participant)
):
    """Create or refresh a session."""
    create_flag = request.query_params.get("create", "false").lower() == "true"
    
    if not participant:
        # Check if authentication is disabled (for testing)
        auth_disabled = True  # For development/testing
        
        if not auth_disabled:
            return problem_response(403, "authentication_required")
        
        if create_flag:
            # Create anonymous session
            uid = DatabaseActor.create_uid()
            csrf_token = generate_csrf_token()
            
            session_data = {
                "uid": uid,
                "email": None,
                "csrf_token": csrf_token,
                "authenticated": False,
            }
            request.state.session = session_data
            
            # Set session cookie
            response.set_cookie(
                key="particiapi_session",
                value=f"{uid}:{csrf_token}",
                httponly=True,
                secure=False,
                samesite="lax",
            )
            
            return {
                "csrf_token": csrf_token,
                "authenticated": False,
            }
    
    # Return existing session info
    session = getattr(request.state, "session", {})
    return {
        "csrf_token": session.get("csrf_token", ""),
        "authenticated": session.get("authenticated", False),
    }


# =====================
# Conversation Endpoint
# =====================

@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    request: Request,
    participant: Optional[Dict] = Depends(get_current_participant)
):
    """Get conversation details."""
    try:
        zid = BaseActor.get_zid_by_zinvite(conversation_id)
        if not zid:
            raise ConversationNotFoundError()
        
        conv = BaseActor.read_conversation(zid)
        if not conv:
            raise ConversationNotFoundError()
        
        settings = conv.settings or {}
        
        # Get seed statements
        all_comments = BaseActor.list_comments_by_conversation_id(zid)
        seed_statements = {}
        for c in all_comments:
            if getattr(c, 'is_seed', False):
                seed_statements[str(c.id)] = {
                    "id": c.id,
                    "text": c.text_field,
                    "is_meta": getattr(c, 'is_meta', False),
                    "is_seed": True,
                }
        
        return {
            "topic": conv.title or "",
            "description": conv.description or "",
            "linkURL": settings.get("link_url", ""),
            "is_active": not conv.is_archived,
            "statements_allowed": bool(settings.get("write_type", 1)),
            "notifications_available": bool(settings.get("subscribe_type", 1)),
            "results_available": settings.get("vis_type", 0) != 0,
            "seed_statements": seed_statements,
        }
    except ConversationNotFoundError:
        return problem_response(404, "not_found", "Conversation not found")


# =====================
# Results Endpoint
# =====================

@router.get("/conversations/{conversation_id}/results/")
async def get_results(
    conversation_id: str,
    request: Request,
    participant: Optional[Dict] = Depends(get_current_participant)
):
    """Get conversation results (consensus and group representation)."""
    try:
        zid = BaseActor.get_zid_by_zinvite(conversation_id)
        if not zid:
            raise ConversationNotFoundError()
        
        # Check if results are available
        conv = BaseActor.read_conversation(zid)
        if not conv:
            raise ConversationNotFoundError()
        
        settings = conv.settings or {}
        if settings.get("vis_type", 0) == 0:
            raise ResultsNotAvailableError()
        
        # Get math results from database
        results = DatabaseActor.get_results(zid)
        
        # Convert to ParticiAPI format
        def convert_group_results(group_results):
            return {
                "agree": [
                    {
                        "statement_id": r.statement_id,
                        "statement_text": r.statement_text,
                        "value": r.value,
                    }
                    for r in group_results.agree
                ],
                "disagree": [
                    {
                        "statement_id": r.statement_id,
                        "statement_text": r.statement_text,
                        "value": r.value,
                    }
                    for r in group_results.disagree
                ],
            }
        
        return {
            "majority": convert_group_results(results.majority),
            "groups": [convert_group_results(g) for g in results.groups],
        }
    except ConversationNotFoundError:
        return problem_response(404, "not_found", "Conversation not found")
    except ResultsNotAvailableError:
        return problem_response(403, "results_not_available", "Results not available")


# =====================
# Statements Endpoints
# =====================

@router.get("/conversations/{conversation_id}/statements/")
async def get_statements(
    conversation_id: str,
    request: Request,
    participant: Optional[Dict] = Depends(get_current_participant)
):
    """Get all statements in a conversation."""
    try:
        zid = BaseActor.get_zid_by_zinvite(conversation_id)
        if not zid:
            raise ConversationNotFoundError()
        
        # Get conversation to check moderation settings
        conv = BaseActor.read_conversation(zid)
        if not conv:
            raise ConversationNotFoundError()
        
        settings = conv.settings or {}
        strict_moderation = settings.get("strict_moderation", False)
        
        # Get all comments
        all_comments = BaseActor.list_comments_by_conversation_id(zid)
        
        statements = {}
        for c in all_comments:
            # Filter by moderation status
            if strict_moderation and c.moderation_status != 1:
                continue
            elif not strict_moderation and c.moderation_status < 0:
                continue
            
            statements[str(c.id)] = {
                "id": c.id,
                "text": c.text_field,
                "is_meta": getattr(c, 'is_meta', False),
                "is_seed": getattr(c, 'is_seed', False),
            }
        
        return statements
    except ConversationNotFoundError:
        return problem_response(404, "not_found", "Conversation not found")


@router.post("/conversations/{conversation_id}/statements/")
async def create_statement(
    conversation_id: str,
    statement_input: StatementInput,
    request: Request,
    session: Dict = Depends(require_session)
):
    """Submit a new statement."""
    # CSRF check
    csrf_error = check_csrf(request, session)
    if csrf_error:
        return csrf_error
    
    try:
        zid = BaseActor.get_zid_by_zinvite(conversation_id)
        if not zid:
            raise ConversationNotFoundError()
        
        uid = session.get("uid")
        
        # Create statement object
        statement = Statement(text=statement_input.text)
        
        # Add statement via database actor
        created = DatabaseActor.add_statement(zid, uid, statement)
        
        return {
            "id": created.id,
            "text": created.text_field,
            "is_meta": getattr(created, 'is_meta', False),
            "is_seed": getattr(created, 'is_seed', False),
        }, 201
    except ConversationNotFoundError:
        return problem_response(404, "not_found", "Conversation not found")
    except ConversationInactiveError:
        return problem_response(403, "conversation_inactive", "Conversation is inactive")
    except StatementsNotAllowedError:
        return problem_response(403, "statements_not_allowed", "Statements not allowed")
    except StatementExistsError:
        return problem_response(409, "statement_exists", "Statement already exists")


# =====================
# Participant Endpoint
# =====================

@router.get("/conversations/{conversation_id}/participant")
async def get_participant(
    conversation_id: str,
    request: Request,
    participant: Optional[Dict] = Depends(get_current_participant)
):
    """Get participant info for current user."""
    if not participant:
        # Return empty participant for unauthenticated users
        return {
            "votes": [],
            "statements": [],
            "notifications": {"enabled": False, "email": None},
        }
    
    try:
        zid = BaseActor.get_zid_by_zinvite(conversation_id)
        if not zid:
            raise ConversationNotFoundError()
        
        uid = participant.get("uid")
        
        # Get participant data
        ptpt = DatabaseActor.get_participant(zid, uid)
        
        return {
            "votes": ptpt.votes,
            "statements": ptpt.statements,
            "notifications": {
                "enabled": ptpt.notifications.enabled,
                "email": ptpt.notifications.email,
            },
        }
    except ConversationNotFoundError:
        return problem_response(404, "not_found", "Conversation not found")


# =====================
# Notifications Endpoints
# =====================

@router.get("/conversations/{conversation_id}/participant/notifications")
async def get_notifications(
    conversation_id: str,
    request: Request,
    participant: Optional[Dict] = Depends(get_current_participant)
):
    """Get notification settings for current participant."""
    if not participant:
        return {"enabled": False, "email": None}
    
    try:
        zid = BaseActor.get_zid_by_zinvite(conversation_id)
        if not zid:
            raise ConversationNotFoundError()
        
        uid = participant.get("uid")
        notifications = DatabaseActor.get_notifications(zid, uid)
        
        return {
            "enabled": notifications.enabled,
            "email": notifications.email,
        }
    except ConversationNotFoundError:
        return problem_response(404, "not_found", "Conversation not found")


@router.put("/conversations/{conversation_id}/participant/notifications")
async def set_notifications(
    conversation_id: str,
    notifications_input: NotificationsInput,
    request: Request,
    session: Dict = Depends(require_session)
):
    """Set notification settings for current participant."""
    # CSRF check
    csrf_error = check_csrf(request, session)
    if csrf_error:
        return csrf_error
    
    try:
        zid = BaseActor.get_zid_by_zinvite(conversation_id)
        if not zid:
            raise ConversationNotFoundError()
        
        uid = session.get("uid")
        
        # Get user email
        user = BaseActor.read_user(uid)
        email = user.email if user else None
        
        # Create notifications object
        notifications = Notifications(
            enabled=notifications_input.enabled,
            email=email,
        )
        
        # Set notifications
        updated = DatabaseActor.set_notifications(uid, notifications, zid)
        
        return {
            "enabled": updated.enabled,
            "email": updated.email,
        }
    except ConversationNotFoundError:
        return problem_response(404, "not_found", "Conversation not found")
    except ConversationInactiveError:
        return problem_response(403, "conversation_inactive", "Conversation is inactive")
    except NotificationsNotAvailableError:
        return problem_response(403, "notifications_not_available", "Notifications not available")
    except EmailAddressMissingError:
        return problem_response(422, "email_address_missing", "Email address required")


# =====================
# Votes Endpoint
# =====================

@router.put("/conversations/{conversation_id}/votes/{tid}")
async def submit_vote(
    conversation_id: str,
    tid: int,
    vote_input: VoteInput,
    request: Request,
    session: Dict = Depends(require_session)
):
    """Submit a vote on a statement."""
    # CSRF check
    csrf_error = check_csrf(request, session)
    if csrf_error:
        return csrf_error
    
    try:
        zid = BaseActor.get_zid_by_zinvite(conversation_id)
        if not zid:
            raise ConversationNotFoundError()
        
        uid = session.get("uid")
        
        # Validate vote value
        if vote_input.value not in [-1, 0, 1]:
            return problem_response(400, "malformed_request", "Invalid vote value")
        
        # Create vote object
        vote = VoteResponse(value=VoteValue(vote_input.value))
        
        # Add vote
        DatabaseActor.add_vote(zid, uid, tid, vote)
        
        return {
            "value": vote_input.value,
        }
    except ConversationNotFoundError:
        return problem_response(404, "not_found", "Conversation not found")
    except StatementNotFoundError:
        return problem_response(404, "not_found", "Statement not found")
    except ConversationInactiveError:
        return problem_response(403, "conversation_inactive", "Conversation is inactive")
    except VotingNotAllowedError:
        return problem_response(403, "voting_not_allowed", "Cannot vote on own statement")
