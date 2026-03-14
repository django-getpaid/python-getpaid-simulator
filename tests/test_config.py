"""Tests for configuration system."""

import os

import pytest

from getpaid_simulator.core.config import SimulatorConfig


class TestConfigDefaults:
    """Test default configuration values."""

    def test_config_defaults(self) -> None:
        """Test that SimulatorConfig defaults match hardcoded values."""
        config = SimulatorConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 9000
        assert config.payu_second_key == "b6ca15b0d1020e8094d9b5f8d163db54"
        assert config.paynow_signature_key == "sim-paynow-key-default"
        assert config.paynow_api_key == "sim-paynow-api-key"
        assert config.paynow_notify_url == ""
        assert config.webhook_timeout == 5.0
        assert config.webhook_max_retries == 3
        assert config.log_level == "INFO"


class TestConfigFromEnv:
    """Test environment variable loading."""

    def test_config_from_env_no_vars(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test from_env with no env vars uses defaults."""
        # Clear any existing env vars
        for key in [
            "SIMULATOR_HOST",
            "SIMULATOR_PORT",
            "SIMULATOR_PAYU_SECOND_KEY",
            "SIMULATOR_PAYNOW_SIGNATURE_KEY",
            "SIMULATOR_PAYNOW_API_KEY",
            "SIMULATOR_PAYNOW_NOTIFY_URL",
            "SIMULATOR_WEBHOOK_TIMEOUT",
            "SIMULATOR_WEBHOOK_MAX_RETRIES",
            "SIMULATOR_LOG_LEVEL",
        ]:
            monkeypatch.delenv(key, raising=False)

        config = SimulatorConfig.from_env()
        assert config.host == "0.0.0.0"
        assert config.port == 9000
        assert config.payu_second_key == "b6ca15b0d1020e8094d9b5f8d163db54"

    def test_config_from_env_with_port_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test from_env with SIMULATOR_PORT override."""
        monkeypatch.setenv("SIMULATOR_PORT", "8080")
        config = SimulatorConfig.from_env()
        assert config.port == 8080
        assert config.host == "0.0.0.0"  # Other values use defaults

    def test_config_from_env_with_payu_key_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test from_env with SIMULATOR_PAYU_SECOND_KEY override."""
        monkeypatch.setenv("SIMULATOR_PAYU_SECOND_KEY", "custom-payu-key")
        config = SimulatorConfig.from_env()
        assert config.payu_second_key == "custom-payu-key"
        assert config.port == 9000  # Other values use defaults

    def test_config_from_env_with_multiple_overrides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test from_env with multiple env var overrides."""
        monkeypatch.setenv("SIMULATOR_HOST", "127.0.0.1")
        monkeypatch.setenv("SIMULATOR_PORT", "8888")
        monkeypatch.setenv("SIMULATOR_PAYU_SECOND_KEY", "custom-key")
        monkeypatch.setenv("SIMULATOR_LOG_LEVEL", "DEBUG")

        config = SimulatorConfig.from_env()
        assert config.host == "127.0.0.1"
        assert config.port == 8888
        assert config.payu_second_key == "custom-key"
        assert config.log_level == "DEBUG"
        # Unset values still use defaults
        assert config.webhook_timeout == 5.0

    def test_config_from_env_with_paynow_vars(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test from_env with PayNow-specific overrides."""
        monkeypatch.setenv("SIMULATOR_PAYNOW_SIGNATURE_KEY", "paynow-sig")
        monkeypatch.setenv("SIMULATOR_PAYNOW_API_KEY", "paynow-api")
        monkeypatch.setenv(
            "SIMULATOR_PAYNOW_NOTIFY_URL", "https://example.com/notify"
        )

        config = SimulatorConfig.from_env()
        assert config.paynow_signature_key == "paynow-sig"
        assert config.paynow_api_key == "paynow-api"
        assert config.paynow_notify_url == "https://example.com/notify"

    def test_config_from_env_float_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test from_env with float timeout conversion."""
        monkeypatch.setenv("SIMULATOR_WEBHOOK_TIMEOUT", "10.5")
        config = SimulatorConfig.from_env()
        assert config.webhook_timeout == 10.5
        assert isinstance(config.webhook_timeout, float)

    def test_config_from_env_int_retries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test from_env with int retries conversion."""
        monkeypatch.setenv("SIMULATOR_WEBHOOK_MAX_RETRIES", "5")
        config = SimulatorConfig.from_env()
        assert config.webhook_max_retries == 5
        assert isinstance(config.webhook_max_retries, int)
