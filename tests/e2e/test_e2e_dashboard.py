"""E2E tests for dashboard UI using Playwright."""

import pytest
from playwright.async_api import Page


@pytest.mark.asyncio
async def test_e2e_dashboard_multi_provider(
    page: Page,
    create_payu_order: callable,
    create_paynow_payment: callable,
    live_server: str,
) -> None:
    """Test dashboard displays multiple provider payments."""
    await create_payu_order(
        notify_url=f"{live_server}/webhook",
        continue_url=f"{live_server}/return",
        ext_order_id="DASH-PAYU-1",
    )

    await create_paynow_payment(
        continue_url=f"{live_server}/paynow-return",
        external_id="DASH-PAYNOW-1",
    )

    await page.goto(f"{live_server}/sim/dashboard")

    content = await page.content()
    assert "PayU" in content
    assert "PayNow" in content

    cards = page.locator(".payment-card")
    count = await cards.count()
    assert count >= 2

    await page.screenshot(path=".sisyphus/evidence/task-21-e2e-dashboard.png")


@pytest.mark.asyncio
async def test_e2e_dashboard_empty_state(
    page: Page,
    live_server: str,
) -> None:
    """Test dashboard displays empty state when no payments exist."""
    await page.goto(f"{live_server}/sim/dashboard")

    content = await page.content()
    assert "No payments" in content or "empty" in content.lower()
