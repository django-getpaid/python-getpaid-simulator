# Changelog

## v3.2.0 (2026-07-04)

### Fixed

- Build tooling resolves `python-getpaid-core`, `python-getpaid-payu`, and
  `python-getpaid-paynow` from PyPI (`>=3.1.0`); the local
  `[tool.uv.sources]` overrides pointing at sibling checkouts were removed
  and `uv.lock` is now committed so `uv sync --frozen` works in CI.
- Docker image builds from the simulator repository alone (no sibling
  checkouts in the build context) and the compose healthcheck uses the
  Python standard library instead of the unavailable `curl` binary.
- The production image no longer installs development tooling; provider
  plugins install via the dedicated `providers` dependency group.
- Removed the vestigial PostgreSQL service from `compose.test.yml` — the
  simulator is stateless and nothing read `TEST_DATABASE_URL`.
- Unknown providers are an explicit error (`UnknownProviderError`) instead
  of silently defaulting to PayU in the state machine and storage.
- `InvalidTransitionError` now carries provider-neutral fields (`code`,
  `message`, `current_state`, `event`); the PayU-shaped `error_response`
  body remains available as a deprecated compatibility property for
  published plugins.
- Decimal amounts are rounded half-up to integer minor units instead of
  being truncated.
- Expired OAuth tokens are purged on token creation and validation.
- `JinjaTemplateEngine` is imported from `litestar.plugins.jinja` and the
  Litestar dependency is capped to `<3.0`.
- The startup banner prints a browsable dashboard URL (`localhost` when
  bound to a wildcard address).
- The release workflow runs only after the CI workflow succeeds on `main`.

## v3.1.0 (2026-06-18)

Ecosystem alignment release.

### Changes

- Version aligned with the published `python-getpaid` 3.1.0 ecosystem
  (`python-getpaid-core`, `python-getpaid-payu`, `python-getpaid-paynow`).
- Provider plugins are exercised against their published 3.1.0 releases.

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
