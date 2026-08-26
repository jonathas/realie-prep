from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import Settings
from app.official_website import ScrapedQuestionBank
from app.schemas import ExtractedOption, ExtractedQuestion, ExtractedQuestionBank


def answers_for(batch: dict[str, object], wrong_from: int = 10) -> list[dict[str, object]]:
    questions = batch["questions"]
    assert isinstance(questions, list)
    return [
        {
            "question_view_id": question["id"],
            "selected_option": "A" if index < wrong_from else "B",
        }
        for index, question in enumerate(questions)
    ]


def extracted_bank() -> ExtractedQuestionBank:
    return ExtractedQuestionBank(
        questions=[
            ExtractedQuestion(
                category=f"Topic {(index // 10) + 1}",
                category_number=(index // 10) + 1,
                question_number=(index % 10) + 1,
                text=f"Question {index + 1}",
                options=[ExtractedOption(label=label, text=f"Option {label}") for label in "ABCD"],
                correct_answer="A",
            )
            for index in range(20)
        ]
    )


def test_health_and_empty_study_session(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}

    response = client.get("/api/quiz/today")
    assert response.status_code == 200
    assert response.json()["bank_empty"] is True
    assert response.json()["batches"] == []


def test_quiz_api_flow_restores_results_and_updates_stats(
    client: TestClient, question_bank: object
) -> None:
    today = client.get("/api/quiz/today")
    assert today.status_code == 200
    batch = today.json()["batches"][0]
    assert len(batch["questions"]) == 10
    assert batch["submitted"] is False

    blocked = client.post("/api/quiz/batches", json={"mode": "unseen"})
    assert blocked.status_code == 409
    assert "Submit the current batch" in blocked.json()["detail"]

    submission = client.post(
        f"/api/quiz/batches/{batch['id']}/submit",
        json={"answers": answers_for(batch, wrong_from=8)},
    )
    assert submission.status_code == 200
    assert submission.json()["score"] == 8
    assert submission.json()["accuracy"] == 80.0

    restored = client.get("/api/quiz/today").json()["batches"][0]
    assert restored["submitted"] is True
    assert restored["score"] == 8
    assert [question["selected_option"] for question in restored["questions"]] == [
        "A",
    ] * 8 + ["B"] * 2

    correct_view = restored["questions"][0]["id"]
    incorrect_view = restored["questions"][-1]["id"]
    assert client.patch(
        f"/api/quiz/views/{correct_view}/mistake", json={"mistake_type": "knowledge"}
    ).status_code == 409
    assert client.patch(
        f"/api/quiz/views/{incorrect_view}/mistake", json={"mistake_type": "knowledge"}
    ).status_code == 204

    stats = client.get("/api/stats")
    assert stats.status_code == 200
    assert stats.json()["total_attempts"] == 10
    assert stats.json()["overall_accuracy"] == 80.0
    assert stats.json()["mistakes"]["knowledge"] == 1

    next_batch = client.post("/api/quiz/batches", json={"mode": "unseen"})
    assert next_batch.status_code == 201
    assert next_batch.json()["batch_number"] == 2
    first_question_ids = {question["question_id"] for question in batch["questions"]}
    next_question_ids = {
        question["question_id"] for question in next_batch.json()["questions"]
    }
    assert first_question_ids.isdisjoint(next_question_ids)


def test_quiz_api_rejects_incomplete_duplicate_and_repeated_submissions(
    client: TestClient, question_bank: object
) -> None:
    batch = client.get("/api/quiz/today").json()["batches"][0]
    answers = answers_for(batch)

    incomplete = client.post(
        f"/api/quiz/batches/{batch['id']}/submit", json={"answers": answers[:-1]}
    )
    assert incomplete.status_code == 409

    duplicate = client.post(
        f"/api/quiz/batches/{batch['id']}/submit",
        json={"answers": answers + [answers[0]]},
    )
    assert duplicate.status_code == 409

    assert client.post(
        f"/api/quiz/batches/{batch['id']}/submit", json={"answers": answers}
    ).status_code == 200
    repeated = client.post(
        f"/api/quiz/batches/{batch['id']}/submit", json={"answers": answers}
    )
    assert repeated.status_code == 409
    assert repeated.json()["detail"] == "This batch was already submitted"


def test_api_validates_payloads_and_admin_password(
    client: TestClient, settings: Settings, question_bank: object
) -> None:
    batch = client.get("/api/quiz/today").json()["batches"][0]
    answers = answers_for(batch)
    answers[0]["selected_option"] = "E"
    assert client.post(
        f"/api/quiz/batches/{batch['id']}/submit", json={"answers": answers}
    ).status_code == 422

    settings.admin_password = "test-secret"
    assert client.get("/api/admin/status").status_code == 401
    status = client.get("/api/admin/status", headers={"X-Admin-Password": "test-secret"})
    assert status.status_code == 200
    assert status.json()["question_count"] == 20


def test_admin_sync_preview_and_confirmation_round_trip(
    client: TestClient, settings: Settings
) -> None:
    settings.admin_password = "test-secret"
    headers = {"X-Admin-Password": "test-secret"}
    scraped = ScrapedQuestionBank(
        bank=extracted_bank(),
        source_url="https://example.test/official-bank/",
        sha256="d" * 64,
        assets={},
    )

    with patch(
        "app.api.OfficialWebsiteScraper.scrape", new=AsyncMock(return_value=scraped)
    ):
        preview = client.post("/api/admin/sync/preview", headers=headers)

    assert preview.status_code == 200
    assert preview.json()["valid"] is True
    assert preview.json()["question_count"] == 20
    token = preview.json()["token"]

    confirmation = client.post(f"/api/admin/sync/{token}/confirm", headers=headers)
    assert confirmation.status_code == 200
    assert confirmation.json()["question_count"] == 20
    assert confirmation.json()["option_count"] == 80
    assert confirmation.json()["source_url"] == scraped.source_url

    with patch(
        "app.api.OfficialWebsiteScraper.scrape", new=AsyncMock(return_value=scraped)
    ):
        duplicate = client.post("/api/admin/sync/preview", headers=headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == ["The official question bank is already up to date"]
