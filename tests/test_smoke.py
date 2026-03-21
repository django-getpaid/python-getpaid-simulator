"""Smoke tests for getpaid-simulator."""

import pytest

import getpaid_simulator


def test_version():
    """Test that version is accessible."""
    assert getpaid_simulator.__version__ == "3.0.0a3"


@pytest.mark.asyncio
async def test_health_endpoint(test_client):
    """Test health endpoint returns OK."""
    response = await test_client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "getpaid-simulator"
    assert body["status"] in {"ok", "degraded"}
    assert isinstance(body["loadedProviders"], list)
    assert isinstance(body["failedProviders"], list)
