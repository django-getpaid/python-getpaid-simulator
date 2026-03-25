"""Smoke tests for getpaid-simulator."""

from pathlib import Path
import tomllib

import pytest

import getpaid_simulator


def test_version():
    """Test that version is accessible."""
    assert getpaid_simulator.__version__ == "3.0.0a4"


def test_e2e_core_dependency_floor():
    """E2E dependency group requires the published core alpha."""
    pyproject_data = tomllib.loads(Path("pyproject.toml").read_text())
    assert (
        "python-getpaid-core>=3.0.0a4"
        in pyproject_data["dependency-groups"]["e2e"]
    )


def test_dev_provider_dependency_floors():
    """Simulator dev environment tracks published provider alpha floors."""
    pyproject_data = tomllib.loads(Path("pyproject.toml").read_text())
    dev_dependencies = pyproject_data["dependency-groups"]["dev"]
    assert "python-getpaid-core>=3.0.0a4" in dev_dependencies
    assert "python-getpaid-payu>=3.0.0a4" in dev_dependencies
    assert "python-getpaid-paynow>=3.0.0a4" in dev_dependencies


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
