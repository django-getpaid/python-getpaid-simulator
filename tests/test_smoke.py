"""Smoke tests for getpaid-simulator."""

import pytest

import getpaid_simulator


def test_version():
    """Test that version is accessible."""
    assert getpaid_simulator.__version__ == "0.1.0a1"


@pytest.mark.asyncio
async def test_health_endpoint(test_client):
    """Test health endpoint returns OK."""
    response = await test_client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "getpaid-simulator"}
