from pathlib import Path

from tests.e2e.conftest import get_chromium_launch_kwargs


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_compose_test_uses_isolated_services_without_host_ports() -> None:
    content = (REPO_ROOT / "compose.test.yml").read_text()

    assert "testdb:" in content
    assert "tests:" in content
    assert "dockerfile: getpaid-simulator/Dockerfile.test" in content
    assert "condition: service_healthy" in content
    assert (
        "TEST_DATABASE_URL: postgresql://test_user:test_password@testdb:5432/test_db"
        in content
    )
    assert "ports:" not in content


def test_dockerfile_test_installs_e2e_dependencies() -> None:
    content = (REPO_ROOT / "Dockerfile.test").read_text()

    assert "FROM python:3.12-slim" in content
    assert "COPY getpaid-core/ /app/getpaid-core/" in content
    assert "COPY getpaid-payu/ /app/getpaid-payu/" in content
    assert "COPY getpaid-paynow/ /app/getpaid-paynow/" in content
    assert "COPY getpaid-simulator/ /app/getpaid-simulator/" in content
    assert "uv sync --frozen --group e2e" in content
    assert (
        'ENV PLAYWRIGHT_BROWSERS_PATH="/app/getpaid-simulator/.cache/ms-playwright"'
        in content
    )
    assert "uv run playwright install chromium" in content
    assert content.index("PLAYWRIGHT_BROWSERS_PATH") < content.index(
        "uv run playwright install chromium"
    )


def test_makefile_exposes_unit_integration_and_e2e_targets() -> None:
    content = (REPO_ROOT / "Makefile").read_text()

    assert (
        ".PHONY: test test-unit test-integration test-e2e test-build test-down"
        in content
    )
    assert "test-unit:" in content
    assert "test-integration:" in content
    assert "test-e2e:" in content
    assert "docker compose -f compose.test.yml run --rm tests" in content


def test_chromium_launch_uses_playwright_bundle_by_default(
    monkeypatch,
) -> None:
    monkeypatch.delenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE", raising=False)

    kwargs = get_chromium_launch_kwargs()

    assert kwargs == {
        "headless": True,
        "args": [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    }


def test_chromium_launch_allows_explicit_executable_override(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PLAYWRIGHT_CHROMIUM_EXECUTABLE",
        "/usr/bin/chromium",
    )

    kwargs = get_chromium_launch_kwargs()

    assert kwargs.get("executable_path") == "/usr/bin/chromium"
