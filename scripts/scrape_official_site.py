"""Download and validate the official online question bank for seed generation."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.official_website import OFFICIAL_BANK_URL, OfficialWebsiteScraper


async def run(url: str, output: Path, assets_dir: Path) -> None:
    scraped = await OfficialWebsiteScraper(url).scrape()
    output.write_text(scraped.bank.model_dump_json(indent=2), encoding="utf-8")
    assets_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in scraped.assets.items():
        (assets_dir / filename).write_bytes(content)
    print(f"Validated {len(scraped.bank.questions)} questions")
    print(f"Source: {scraped.source_url}")
    print(f"SHA-256: {scraped.sha256}")
    print(f"Assets: {len(scraped.assets)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=OFFICIAL_BANK_URL)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.url, args.output, args.assets))


if __name__ == "__main__":
    main()
