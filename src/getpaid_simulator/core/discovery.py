from __future__ import annotations

from importlib.metadata import EntryPoint
from importlib.metadata import entry_points
from pathlib import Path


ENTRY_POINT_GROUP = "getpaid.backends"
PROVIDERS_DIR = Path(__file__).resolve().parent.parent / "providers"
PREFERRED_PROVIDER_ORDER = ("payu", "paynow")


def discover_providers() -> list[str]:
    discovered_from_entry_points = _discover_from_entry_points()
    if discovered_from_entry_points:
        return discovered_from_entry_points
    return _discover_from_provider_directories()


def _discover_from_entry_points() -> list[str]:
    eps: list[EntryPoint] = list(entry_points(group=ENTRY_POINT_GROUP))
    return _order_provider_slugs(
        [entry_point.name for entry_point in eps if entry_point.name]
    )


def _discover_from_provider_directories() -> list[str]:
    if not PROVIDERS_DIR.exists():
        return []

    return _order_provider_slugs(
        [
            path.name
            for path in PROVIDERS_DIR.iterdir()
            if path.is_dir() and not path.name.startswith("_")
        ]
    )


def _order_provider_slugs(provider_slugs: list[str]) -> list[str]:
    seen: set[str] = set()
    deduplicated: list[str] = []
    for provider_slug in provider_slugs:
        if provider_slug in seen:
            continue
        seen.add(provider_slug)
        deduplicated.append(provider_slug)

    preferred = [
        provider_slug
        for provider_slug in PREFERRED_PROVIDER_ORDER
        if provider_slug in deduplicated
    ]
    remaining: list[str] = sorted(
        [
            provider_slug
            for provider_slug in deduplicated
            if provider_slug not in PREFERRED_PROVIDER_ORDER
        ]
    )
    return preferred + remaining
