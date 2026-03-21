"""E2E tests for PayU payment flows using Playwright."""

import httpx
import pytest
from playwright.async_api import Page


@pytest.mark.asyncio
async def test_e2e_payu_complete_flow(
    page: Page,
    create_payu_order: callable,
    live_server: str,
) -> None:
    """Test complete PayU payment flow through browser."""
    order_id, redirect_uri, token = await create_payu_order(
        notify_url=f"{live_server}/webhook",
        continue_url=f"{live_server}/return",
    )

    await page.goto(redirect_uri)

    content = await page.content()
    assert "PayU" in content
    assert "SIMULATOR" in content

    approve_button = page.locator("button[value='approve']")
    await approve_button.click()

    await page.wait_for_url(f"{live_server}/return", timeout=5000)

    await page.screenshot(
        path=".sisyphus/evidence/task-21-e2e-payu-complete.png"
    )

    async with httpx.AsyncClient() as client:
        order_response = await client.get(
            f"{live_server}/payu/api/v2_1/orders/{order_id}",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )
        assert order_response.status_code == 200
        order_data = order_response.json()
        assert order_data["orders"][0]["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_e2e_payu_rejection_flow(
    page: Page,
    create_payu_order: callable,
    live_server: str,
) -> None:
    """Test PayU payment rejection flow through browser."""
    order_id, redirect_uri, token = await create_payu_order(
        notify_url=f"{live_server}/webhook",
        continue_url=f"{live_server}/return",
        ext_order_id="TEST-E2E-REJECT",
    )

    await page.goto(redirect_uri)

    reject_button = page.locator("button[value='reject']")
    await reject_button.click()

    await page.wait_for_url(f"{live_server}/return", timeout=5000)

    await page.screenshot(
        path=".sisyphus/evidence/task-21-e2e-payu-rejection.png"
    )

    async with httpx.AsyncClient() as client:
        order_response = await client.get(
            f"{live_server}/payu/api/v2_1/orders/{order_id}",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )
        assert order_response.status_code == 200
        order_data = order_response.json()
        assert order_data["orders"][0]["status"] == "CANCELED"
