from pathlib import Path


def test_legacy_provider_modules_are_removed() -> None:
    providers_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "getpaid_simulator"
        / "providers"
    )

    assert (
        sorted(
            path.relative_to(providers_dir).as_posix()
            for path in providers_dir.glob("**/*.py")
        )
        == []
    )
