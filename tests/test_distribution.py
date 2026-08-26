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


def test_nginx_never_shadows_persistent_question_images() -> None:
    nginx = (ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    assert "location /question-images/ {\n        proxy_pass http://api:8000;" in nginx
    assert "@dynamic_question_image" not in nginx


def test_nginx_exposes_openapi_documentation() -> None:
    nginx = (ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    for route in ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"):
        assert f"location = {route}" in nginx


def test_frontend_uses_only_self_hosted_fonts() -> None:
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    package = (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
    main = (ROOT / "frontend" / "src" / "main.tsx").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in index
    assert "fonts.gstatic.com" not in index
    assert "@fontsource-variable/inter" in package and "@fontsource-variable/inter" in main
    assert "@fontsource-variable/lora" in package and "@fontsource-variable/lora" in main
