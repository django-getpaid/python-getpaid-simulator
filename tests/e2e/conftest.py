"""E2E test configuration with Playwright and live server."""

import asyncio
import socket
from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import urlsplit

import httpx
import pytest
import uvicorn
from playwright.async_api import Browser
from playwright.async_api import Page
from playwright.async_api import async_playwright

from getpaid_simulator.app import create_app


def _find_free_port() -> int:
    """Find a free port for the test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


@pytest.fixture
async def live_server() -> AsyncGenerator[str, None]:
    """Start uvicorn server for E2E tests."""
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    config = uvicorn.Config(
        create_app(),
        host="127.0.0.1",
        port=port,
        log_level="error",
        access_log=False,
    )
    server = uvicorn.Server(config)

    task = asyncio.create_task(server.serve())

    for _ in range(100):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{base_url}/", timeout=1.0)
                if response.status_code == 200:
                    break
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass
        await asyncio.sleep(0.1)
    else:
        task.cancel()
        raise RuntimeError("Failed to start uvicorn server")

    yield base_url

    server.should_exit = True
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.fixture
async def browser() -> AsyncGenerator[Browser, None]:
    """Playwright browser instance with system Chromium."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/chromium",
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        yield browser
        await browser.close()


@pytest.fixture
async def page(browser: Browser) -> AsyncGenerator[Page, None]:
    """Playwright page for each test."""
    page = await browser.new_page()
    yield page
    await page.close()


@pytest.fixture
async def create_payu_order(
    live_server: str,
) -> AsyncGenerator[Any, None]:
    """Helper to create PayU order via API."""

    async def _create(
        notify_url: str,
        continue_url: str,
        ext_order_id: str = "TEST-E2E-ORDER",
    ) -> tuple[str, str, str]:
        host_header = urlsplit(live_server).netloc

        async with httpx.AsyncClient() as client:
            oauth_response = await client.post(
                f"{live_server}/payu/pl/standard/user/oauth/authorize",
                data={
                    "grant_type": "client_credentials",
                    "client_id": "145227",
                    "client_secret": "test_secret",
                },
            )
            assert oauth_response.status_code == 200
            token = oauth_response.json()["access_token"]

            order_payload = {
                "notifyUrl": notify_url,
                "customerIp": "127.0.0.1",
                "merchantPosId": "145227",
                "description": "E2E Test Order",
                "currencyCode": "PLN",
                "totalAmount": "21000",
                "extOrderId": ext_order_id,
                "continueUrl": continue_url,
                "buyer": {
                    "email": "e2e@example.com",
                    "phone": "654111654",
                    "firstName": "E2E",
                    "lastName": "Test",
                    "language": "pl",
                },
                "products": [
                    {
                        "name": "E2E Product",
                        "unitPrice": "21000",
                        "quantity": "1",
                    }
                ],
            }

            order_response = await client.post(
                f"{live_server}/payu/api/v2_1/orders",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Host": host_header,
                },
                json=order_payload,
                follow_redirects=False,
            )
            assert order_response.status_code == 302
            body = order_response.json()
            order_id = body["orderId"]
            redirect_uri = body["redirectUri"]

            return (order_id, redirect_uri, token)

    yield _create


@pytest.fixture
async def create_paynow_payment(
    live_server: str,
) -> AsyncGenerator[Any, None]:
    """Helper to create PayNow payment via API."""

    async def _create(
        continue_url: str,
        external_id: str = "TEST-E2E-PAYNOW",
    ) -> tuple[str, str]:
        async with httpx.AsyncClient() as client:
            payment_payload = {
                "amount": 10000,
                "currency": "PLN",
                "externalId": external_id,
                "description": "E2E PayNow Test",
                "buyer": {
                    "email": "e2e-paynow@example.com",
                },
                "continueUrl": continue_url,
            }

            response = await client.post(
                f"{live_server}/paynow/v3/payments",
                json=payment_payload,
                headers={
                    "Api-Key": "test-api-key",
                    "Signature": "test-signature",
                    "Idempotency-Key": external_id,
                },
            )
            assert response.status_code == 201
            body = response.json()
            payment_id = body["paymentId"]
            redirect_uri = body["redirectUrl"]

            return (payment_id, redirect_uri)

    yield _create
