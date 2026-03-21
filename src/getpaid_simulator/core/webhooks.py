"""Generic webhook delivery helpers for simulator plugins."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx


if TYPE_CHECKING:
    from collections.abc import Mapping


class WebhookTransport:
    """Generic webhook transport with retry handling."""

    def __init__(
        self,
        timeout: float = 5.0,
        retry_delay: float = 0.0,
        max_retries: int = 1,
    ) -> None:
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.max_retries = max_retries

    async def deliver(
        self,
        *,
        url: str,
        body: bytes,
        headers: Mapping[str, str],
    ) -> bool:
        """Send webhook payload with retry handling."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            attempts = self.max_retries + 1
            for attempt in range(attempts):
                try:
                    response = await client.post(
                        url, content=body, headers=headers
                    )
                    if 400 <= response.status_code < 500:
                        return False
                    if 200 <= response.status_code < 300:
                        return True
                    if attempt < attempts - 1:
                        await asyncio.sleep(self.retry_delay)
                        continue
                    return False
                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.RequestError,
                ):
                    if attempt < attempts - 1:
                        await asyncio.sleep(self.retry_delay)
                        continue
                    return False
        return False
