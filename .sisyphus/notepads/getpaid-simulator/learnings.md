# Task 19: CLI Entry Point - Learnings

## Implementation Summary
- Implemented CLI entry point in `__main__.py` with argparse for host/port/log-level arguments
- Environment variables take precedence over defaults, CLI args override env vars
- Created startup banner with ASCII art showing version, warning, providers, and dashboard URL
- Added [project.scripts] entry in pyproject.toml for `getpaid-simulator` command
- All 137 tests pass (131 baseline + 6 new CLI tests)

## Key Patterns
1. **Config precedence**: defaults < environment vars < CLI arguments
   - Load from env first via `SimulatorConfig.from_env()`
   - Then override with CLI args if provided (check `is not None`)
2. **Startup banner**: Uses `__version__` from `__init__.py` and `discover_providers()` for dynamic content
3. **Log level handling**: uvicorn expects lowercase log level, config stores uppercase
   - Conversion happens in main: `log_level=config.log_level.lower()`
4. **Testing mocked uvicorn**: Use `patch("getpaid_simulator.__main__.uvicorn.run")` to avoid starting server

## Decisions
- argparse chosen for simplicity (not click/typer)
- Banner printed before uvicorn.run() for immediate user feedback
- Log level choices enforced at parser level: DEBUG/INFO/WARNING/ERROR
- Script entry point uses format: `module:function` (getpaid_simulator.__main__:main)

## Known Patterns from Related Tasks
- Task 18 (create_app): Returns Litestar instance, providers accessible via `app.state.discovered_providers`
- Task 10 (config): SimulatorConfig.from_env() handles SIMULATOR_* env var prefix automatically
