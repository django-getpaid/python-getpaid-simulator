.PHONY: test test-unit test-integration test-e2e test-build test-down pip-audit

UNIT_TESTS = \
	tests/test_cli.py \
	tests/test_config.py \
	tests/test_discovery.py \
	tests/test_smoke.py \
	tests/test_storage.py \
	tests/test_state.py \
	tests/test_app.py \
	tests/test_legacy_provider_modules.py \
	tests/test_test_infrastructure.py

INTEGRATION_TESTS = \
	tests/test_ui_dashboard.py \
	tests/test_ui_authorize.py \
	tests/test_payu_oauth.py \
	tests/test_payu_orders.py \
	tests/test_payu_webhooks.py \
	tests/test_payu_refunds.py \
	tests/test_payu_lifecycle.py \
	tests/test_paynow_signing.py \
	tests/test_paynow_payments.py \
	tests/test_paynow_webhooks.py \
	tests/test_paynow_refunds.py \
	tests/test_webhooks.py

E2E_TESTS = \
	tests/e2e/test_e2e_dashboard.py \
	tests/e2e/test_e2e_payu_flow.py

test-unit:
	uv run pytest $(UNIT_TESTS) -x

test-integration: test-build
	docker compose -f compose.test.yml run --rm tests uv run pytest $(INTEGRATION_TESTS) -x

test-e2e: test-build
	docker compose -f compose.test.yml run --rm tests uv run pytest $(E2E_TESTS) -x

test:
	$(MAKE) test-unit
	$(MAKE) test-integration
	$(MAKE) test-e2e

test-build:
	docker compose -f compose.test.yml build

test-down:
	docker compose -f compose.test.yml down -v

pip-audit:
	uv run pip-audit --strict
