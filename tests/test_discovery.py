from types import SimpleNamespace

import getpaid_simulator.core.discovery as discovery


def test_discover_providers_uses_entry_points(monkeypatch):
    def fake_entry_points(*, group: str):
        assert group == "getpaid.backends"
        return [
            SimpleNamespace(name="payu"),
            SimpleNamespace(name="paynow"),
        ]

    monkeypatch.setattr(discovery, "entry_points", fake_entry_points)

    assert discovery.discover_providers() == ["payu", "paynow"]


def test_discover_providers_falls_back_to_provider_directories(
    monkeypatch,
    tmp_path,
):
    (tmp_path / "payu").mkdir()
    (tmp_path / "paynow").mkdir()
    (tmp_path / "README.md").write_text("ignore me", encoding="utf-8")

    monkeypatch.setattr(discovery, "entry_points", lambda *, group: [])
    monkeypatch.setattr(discovery, "PROVIDERS_DIR", tmp_path)

    assert discovery.discover_providers() == ["payu", "paynow"]


def test_discover_providers_returns_only_directories(monkeypatch, tmp_path):
    (tmp_path / "payu").mkdir()
    (tmp_path / "not-a-provider.txt").write_text("ignored", encoding="utf-8")

    monkeypatch.setattr(discovery, "entry_points", lambda *, group: [])
    monkeypatch.setattr(discovery, "PROVIDERS_DIR", tmp_path)

    assert discovery.discover_providers() == ["payu"]
