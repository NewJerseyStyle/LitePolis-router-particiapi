"""Pytest configuration for LitePolis-router-particiapi tests."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_database():
    """Mock database calls for unit tests (not autouse to allow real database in integration tests)."""
    with patch('litepolis_database_particiapi.DatabaseActor') as mock_actor:
        yield mock_actor


@pytest.fixture
def sample_conversation_id():
    """Sample conversation ID for tests."""
    return "test123abc"


@pytest.fixture
def sample_user_id():
    """Sample user ID for tests."""
    return 1
