# Changelog

## v3.0.0 (2026-06-04)

Stable release of the payment gateway simulator host.

### Breaking Changes

- Version bumped from `3.0.0a4` to `3.0.0` (stable).
- Development status changed from `Alpha` to `Production/Stable`.
- Provider dependency floors raised to `>=3.0.0` (from `>=3.0.0a4`).

### Features

- Generic Litestar host with plugin-based provider discovery via entry points.
- Stable SPI (Simulator Provider Interface) with version validation.
- Dashboard UI for managing test payments across providers.
- Webhook transport with retry handling.
- In-memory storage with deep-copy isolation.
- Plugin failure modes: `warn` (default) and `strict`.
- CLI entry point with environment variable and argument configuration.
- Docker support for local development and testing.
- E2E test suite with Playwright.

### Migration from alpha

- Update dependency from `python-getpaid-simulator>=3.0.0a4` to `python-getpaid-simulator>=3.0.0`.
- No API changes — all public interfaces remain stable.
