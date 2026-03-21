"""Test configuration."""

import pytest
from litestar.testing import AsyncTestClient

from getpaid_simulator.app import create_app


@pytest.fixture
def test_client() -> AsyncTestClient:
    """Litestar test client fixture."""
    return AsyncTestClient(app=create_app())
