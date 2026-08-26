from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_official_content_is_not_bundled() -> None:
    assert not (ROOT / "data" / "realieprep_seed.db").exists()
    assert not (ROOT / "frontend" / "public" / "question-images").exists()
    assert "realieprep_seed.db" not in (ROOT / "Dockerfile").read_text(encoding="utf-8")


def test_distribution_is_private_and_empty_by_default() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    entrypoint = (ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8")
    assert "${BIND_ADDRESS:-127.0.0.1}" in compose
    assert "scrape" not in entrypoint
    assert "cp " not in entrypoint
