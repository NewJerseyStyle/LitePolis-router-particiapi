"""Tests for LitePolis-router-particiapi."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    """Create test client."""
    from fastapi import FastAPI
    from litepolis_router_particiapi import router
    
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


class TestSession:
    """Test session endpoints."""
    
    def test_create_session(self, client):
        """Test session creation."""
        response = client.post("/api/session?create=true")
        assert response.status_code == 200
        data = response.json()
        assert "csrf_token" in data
        assert "authenticated" in data


class TestConversations:
    """Test conversation endpoints."""
    
    def test_get_conversation_not_found(self, client):
        """Test getting non-existent conversation."""
        with patch('litepolis_router_particiapi.core.BaseActor.get_zid_by_zinvite') as mock_get_zid:
            mock_get_zid.return_value = None
            response = client.get("/api/conversations/nonexistent")
            assert response.status_code == 404


class TestStatements:
    """Test statement endpoints."""
    
    def test_get_statements_not_found(self, client):
        """Test getting statements for non-existent conversation."""
        with patch('litepolis_router_particiapi.core.BaseActor.get_zid_by_zinvite') as mock_get_zid:
            mock_get_zid.return_value = None
            response = client.get("/api/conversations/nonexistent/statements/")
            assert response.status_code == 404


class TestVotes:
    """Test vote endpoints."""
    
    def test_submit_vote_not_found(self, client):
        """Test voting on non-existent conversation."""
        # First create a session
        session_resp = client.post("/api/session?create=true")
        assert session_resp.status_code == 200
        csrf_token = session_resp.json()["csrf_token"]
        
        with patch('litepolis_router_particiapi.core.BaseActor.get_zid_by_zinvite') as mock_get_zid:
            mock_get_zid.return_value = None
            response = client.put(
                "/api/conversations/nonexistent/votes/1",
                json={"value": -1},
                headers={"X-CSRF-Token": csrf_token}
            )
            assert response.status_code == 404
