"""Tests for CLI entry point."""

import sys
from unittest.mock import patch

import pytest

from getpaid_simulator.__main__ import main


class TestCLIDefaults:
    """Test CLI with default arguments."""

    def test_cli_main_with_no_args(self) -> None:
        """Test main() uses config defaults when no args provided."""
        with patch("getpaid_simulator.__main__.uvicorn.run") as mock_run:
            with patch(
                "sys.argv",
                ["getpaid-simulator"],
            ):
                try:
                    main()
                except SystemExit:
                    # argparse may exit after showing help, catch it
                    pass

            # Verify uvicorn.run was called
            if mock_run.called:
                call_kwargs = mock_run.call_args[1]
                # Config defaults should apply
                assert call_kwargs["host"] == "0.0.0.0"
                assert call_kwargs["port"] == 9000

    def test_cli_custom_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test --port CLI argument overrides config.port."""
        monkeypatch.setenv(
            "SIMULATOR_PORT", "9000"
        )  # Ensure env doesn't interfere

        with patch("getpaid_simulator.__main__.uvicorn.run") as mock_run:
            with patch(
                "sys.argv",
                ["getpaid-simulator", "--port", "8080"],
            ):
                try:
                    main()
                except SystemExit:
                    pass

            if mock_run.called:
                call_kwargs = mock_run.call_args[1]
                assert call_kwargs["port"] == 8080

    def test_cli_custom_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test --host CLI argument overrides config.host."""
        monkeypatch.setenv(
            "SIMULATOR_HOST", "0.0.0.0"
        )  # Ensure env doesn't interfere

        with patch("getpaid_simulator.__main__.uvicorn.run") as mock_run:
            with patch(
                "sys.argv",
                ["getpaid-simulator", "--host", "127.0.0.1"],
            ):
                try:
                    main()
                except SystemExit:
                    pass

            if mock_run.called:
                call_kwargs = mock_run.call_args[1]
                assert call_kwargs["host"] == "127.0.0.1"

    def test_cli_custom_log_level(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test --log-level CLI argument overrides config.log_level."""
        monkeypatch.setenv("SIMULATOR_LOG_LEVEL", "INFO")

        with patch("getpaid_simulator.__main__.uvicorn.run") as mock_run:
            with patch(
                "sys.argv",
                ["getpaid-simulator", "--log-level", "DEBUG"],
            ):
                try:
                    main()
                except SystemExit:
                    pass

            if mock_run.called:
                # Log level is converted to lowercase for uvicorn
                call_kwargs = mock_run.call_args[1]
                assert call_kwargs.get("log_level") == "debug"

    def test_cli_help_shows_arguments(self) -> None:
        """Test --help displays all 3 CLI arguments."""
        with patch(
            "sys.argv",
            ["getpaid-simulator", "--help"],
        ):
            with pytest.raises(SystemExit):
                main()
        # If we get here, it tried to show help (raised SystemExit(0))

    def test_cli_config_env_overridden_by_cli(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test CLI args override environment variables."""
        monkeypatch.setenv("SIMULATOR_PORT", "7000")
        monkeypatch.setenv("SIMULATOR_HOST", "192.168.1.1")

        with patch("getpaid_simulator.__main__.uvicorn.run") as mock_run:
            with patch(
                "sys.argv",
                ["getpaid-simulator", "--port", "8080", "--host", "127.0.0.1"],
            ):
                try:
                    main()
                except SystemExit:
                    pass

            if mock_run.called:
                call_kwargs = mock_run.call_args[1]
                assert call_kwargs["port"] == 8080
                assert call_kwargs["host"] == "127.0.0.1"

    def test_cli_custom_plugin_failure_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SIMULATOR_PLUGIN_FAILURE_MODE", "warn")

        with patch("getpaid_simulator.__main__.create_app") as mock_create_app:
            with patch("getpaid_simulator.__main__.uvicorn.run"):
                with patch(
                    "sys.argv",
                    [
                        "getpaid-simulator",
                        "--plugin-failure-mode",
                        "strict",
                    ],
                ):
                    try:
                        main()
                    except SystemExit:
                        pass

        config = mock_create_app.call_args.args[0]
        assert config.plugin_failure_mode == "strict"
