from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass
from datetime import date
from typing import cast
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup, Tag

from app.schemas import (
    ExtractedOption,
    ExtractedQuestion,
    ExtractedQuestionBank,
    OptionLabel,
)

OFFICIAL_BANK_URL = "https://cestina-pro-cizince.cz/obcanstvi/databanka-uloh/"


class ScrapingError(ValueError):
    pass


@dataclass(frozen=True)
class ScrapedQuestionBank:
    bank: ExtractedQuestionBank
    source_url: str
    sha256: str
    assets: dict[str, bytes]


def _text(tag: Tag) -> str:
    for superscript in tag.find_all("sup"):
        value = superscript.get_text(strip=True)
        superscript.replace_with({"2": "²", "3": "³"}.get(value, value))
    value = re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()
    return re.sub(r"\s+([.,;:?!²³])", r"\1", value)


def parse_official_html(
    content: bytes, source_url: str = OFFICIAL_BANK_URL
) -> tuple[ExtractedQuestionBank, dict[str, str]]:
    soup = BeautifulSoup(content, "html.parser")
    questions: list[ExtractedQuestion] = []
    image_urls: dict[str, str] = {}
    topics = soup.select("h3.subH3")
    for category_number, topic in enumerate(topics, start=1):
        category = _text(topic).strip()
        question_list = topic.find_next_sibling("ol", class_="patnact")
        if not isinstance(question_list, Tag):
            continue
        items = question_list.find_all("li", recursive=False)
        question_number = 0
        for item in items:
            prompt = item.find("div", class_="text")
            alternatives = item.find("ol", class_="alternatives")
            if not isinstance(prompt, Tag) or not isinstance(alternatives, Tag):
                continue
            labels = alternatives.find_all("label")
            if len(labels) != 4:
                raise ScrapingError(f"{category}: expected four answer labels, found {len(labels)}")
            question_number += 1
            stable_key = f"{category_number}.{question_number}"
            options: list[ExtractedOption] = []
            for index, label in enumerate(labels):
                option_label = cast(OptionLabel, "ABCD"[index])
                option_text = re.sub(r"^[ABCD]\)\s*", "", _text(label)) or "Obrázek"
                option_image = label.find("img")
                image_path: str | None = None
                if isinstance(option_image, Tag) and option_image.get("src"):
                    filename = f"{stable_key.replace('.', '-')}-{option_label.lower()}.jpg"
                    image_path = f"/question-images/{filename}"
                    image_urls[filename] = urljoin(source_url, str(option_image["src"]))
                options.append(
                    ExtractedOption(
                        label=option_label,
                        text=option_text,
                        image_path=image_path,
                    )
                )
            answer_node = item.find("span", class_="spravne")
            answer_match = (
                re.search(r"Správná odpověď:\s*([ABCD])", _text(answer_node))
                if isinstance(answer_node, Tag)
                else None
            )
            if not answer_match:
                raise ScrapingError(f"{stable_key}: correct answer not found")
            prompt_image = item.find("div", class_="q_pic")
            image_path = None
            if isinstance(prompt_image, Tag):
                image = prompt_image.find("img")
                if isinstance(image, Tag) and image.get("src"):
                    filename = f"{stable_key.replace('.', '-')}-prompt.jpg"
                    image_path = f"/question-images/{filename}"
                    image_urls[filename] = urljoin(source_url, str(image["src"]))
            result_span = item.find("span", class_="correct")
            official_id = None
            if isinstance(result_span, Tag) and result_span.get("id"):
                official_id = str(result_span["id"]).removeprefix("c_")
            if official_id is None:
                radio = alternatives.find("input", attrs={"type": "radio"})
                if isinstance(radio, Tag) and radio.get("name"):
                    official_id = str(radio["name"]).removeprefix("r_")
            updated_node = item.find("li", class_="datumAktualizace")
            updated_match = (
                re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", _text(updated_node))
                if isinstance(updated_node, Tag)
                else None
            )
            updated = (
                date(
                    int(updated_match.group(3)),
                    int(updated_match.group(2)),
                    int(updated_match.group(1)),
                )
                if updated_match
                else None
            )
            questions.append(
                ExtractedQuestion(
                    category=category,
                    category_number=category_number,
                    question_number=question_number,
                    official_id=official_id,
                    source_updated_on=updated,
                    text=_text(prompt),
                    options=options,
                    correct_answer=cast(OptionLabel, answer_match.group(1)),
                    image_path=image_path,
                )
            )
    return ExtractedQuestionBank(questions=questions), image_urls


class OfficialWebsiteScraper:
    def __init__(self, source_url: str = OFFICIAL_BANK_URL) -> None:
        self.source_url = source_url

    async def scrape(self) -> ScrapedQuestionBank:
        headers = {"User-Agent": "RealiePrep/0.1 (+self-hosted study application)"}
        async with httpx.AsyncClient(follow_redirects=True, timeout=60, headers=headers) as client:
            try:
                response = await client.get(self.source_url)
                response.raise_for_status()
                bank, image_urls = parse_official_html(response.content, str(response.url))
                assets = await self._download_assets(client, image_urls)
            except (httpx.HTTPError, ValueError) as exc:
                raise ScrapingError(f"Could not read the official question bank: {exc}") from exc
        return ScrapedQuestionBank(
            bank=bank,
            source_url=str(response.url),
            sha256=hashlib.sha256(bank.model_dump_json().encode()).hexdigest(),
            assets=assets,
        )

    async def _download_assets(
        self, client: httpx.AsyncClient, image_urls: dict[str, str]
    ) -> dict[str, bytes]:
        async def download(filename: str, url: str) -> tuple[str, bytes]:
            response = await client.get(url)
            response.raise_for_status()
            return filename, response.content

        pairs = await asyncio.gather(
            *(download(filename, url) for filename, url in image_urls.items())
        )
        return dict(pairs)


def source_filename(url: str) -> str:
    host = urlsplit(url).hostname or "official website"
    return f"Official online database ({host})"
