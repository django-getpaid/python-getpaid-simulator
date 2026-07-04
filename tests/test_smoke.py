"""Smoke tests for getpaid-simulator."""

import tomllib
from importlib.metadata import version
from pathlib import Path

import pytest

import getpaid_simulator


def test_version():
    """Source __version__ matches the installed package metadata."""
    assert getpaid_simulator.__version__ == version("python-getpaid-simulator")


def test_provider_dependency_floors():
    """Simulator tracks the published provider dependency floors."""
    pyproject_data = tomllib.loads(Path("pyproject.toml").read_text())
    provider_deps = pyproject_data["dependency-groups"]["providers"]
    assert "python-getpaid-core>=3.1.0" in provider_deps
    assert "python-getpaid-payu>=3.1.0" in provider_deps
    assert "python-getpaid-paynow>=3.1.0" in provider_deps


def test_dev_group_includes_providers():
    """Dev environment installs the provider plugins."""
    pyproject_data = tomllib.loads(Path("pyproject.toml").read_text())
    dev_dependencies = pyproject_data["dependency-groups"]["dev"]
    assert {"include-group": "providers"} in dev_dependencies


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
