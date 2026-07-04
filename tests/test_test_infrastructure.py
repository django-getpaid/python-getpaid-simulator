from pathlib import Path

from tests.e2e.conftest import get_chromium_launch_kwargs


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_compose_test_uses_isolated_services_without_host_ports() -> None:
    content = (REPO_ROOT / "compose.test.yml").read_text()

    assert "tests:" in content
    assert "context: ." in content
    assert "dockerfile: Dockerfile.test" in content
    # The simulator is stateless: no database service or DSN should exist.
    assert "postgres" not in content
    assert "TEST_DATABASE_URL" not in content
    assert "ports:" not in content


def test_dockerfile_test_installs_test_dependencies() -> None:
    content = (REPO_ROOT / "Dockerfile.test").read_text()

    assert "FROM python:3.12-slim" in content
    # The image builds from the simulator repo alone; provider packages
    # come from PyPI via the lockfile, not from sibling checkouts.
    assert "COPY . /app/getpaid-simulator" in content
    assert "COPY getpaid-core/" not in content
    assert "uv sync --frozen" in content
    assert "[tool.uv.sources]" not in content
    browsers_path = '"/app/getpaid-simulator/.cache/ms-playwright"'
    assert f"ENV PLAYWRIGHT_BROWSERS_PATH={browsers_path}" in content
    assert "uv run playwright install chromium" in content
    assert content.index("PLAYWRIGHT_BROWSERS_PATH") < content.index(
        "uv run playwright install chromium"
    )


def test_dockerfile_builds_from_repo_without_dev_tooling() -> None:
    content = (REPO_ROOT / "Dockerfile").read_text()

    assert "FROM python:3.12-slim" in content
    assert "COPY . /app" in content
    assert "COPY getpaid-core/" not in content
    assert "uv sync --frozen --no-dev --group providers" in content
    assert "USER simulator" in content


def test_compose_healthcheck_avoids_curl() -> None:
    content = (REPO_ROOT / "docker-compose.yml").read_text()

    assert "context: ." in content
    assert "curl" not in content
    assert "urllib.request" in content


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


def test_dockerfile_specific_ignore_files_exclude_local_artifacts() -> None:
    for file_name in (
        "Dockerfile.dockerignore",
        "Dockerfile.test.dockerignore",
    ):
        content = (REPO_ROOT / file_name).read_text()
        lines = content.splitlines()

        assert ".git" in lines
        assert ".venv" in lines
        assert "**/__pycache__" in lines
        # No sibling-repo whitelisting: the build context is this repo.
        assert not any("getpaid-" in line for line in lines)


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
