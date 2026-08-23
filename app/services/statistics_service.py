from typing import Any

from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AnswerAttempt, Category, MistakeType, Question, QuestionView


class StatisticsService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def calculate(self) -> dict[str, Any]:
        total_questions = self.db.scalar(select(func.count(Question.id))) or 0
        seen = self.db.scalar(select(func.count(distinct(QuestionView.question_id)))) or 0
        attempts = self.db.scalar(select(func.count(AnswerAttempt.id))) or 0
        correct = (
            self.db.scalar(
                select(func.count(AnswerAttempt.id)).where(AnswerAttempt.correct.is_(True))
            )
            or 0
        )
        first_ids = select(func.min(AnswerAttempt.id)).group_by(AnswerAttempt.question_id)
        first_total = (
            self.db.scalar(
                select(func.count(AnswerAttempt.id)).where(AnswerAttempt.id.in_(first_ids))
            )
            or 0
        )
        first_correct = (
            self.db.scalar(
                select(func.count(AnswerAttempt.id)).where(
                    AnswerAttempt.id.in_(first_ids), AnswerAttempt.correct.is_(True)
                )
            )
            or 0
        )
        first_accuracy = first_correct / first_total * 100 if first_total else 0.0
        categories = self._categories()
        missed = self._missed_twice()
        mistake_counts = {
            kind.value: self.db.scalar(
                select(func.count(AnswerAttempt.id)).where(AnswerAttempt.mistake_type == kind)
            )
            or 0
            for kind in MistakeType
        }
        return {
            "total_questions": total_questions,
            "unique_seen": seen,
            "unique_remaining": max(total_questions - seen, 0),
            "coverage_percent": round(seen / total_questions * 100, 1) if total_questions else 0,
            "total_attempts": attempts,
            "correct": correct,
            "incorrect": attempts - correct,
            "overall_accuracy": round(correct / attempts * 100, 1) if attempts else 0,
            "first_attempt_accuracy": round(first_accuracy, 1),
            "passing_grade_percent": self.settings.passing_grade_percent,
            "passing_difference": round(first_accuracy - self.settings.passing_grade_percent, 1),
            "mistakes": mistake_counts,
            "categories": categories,
            "weakest_categories": [
                row
                for row in categories
                if row["attempts"] >= self.settings.weak_topic_min_attempts
            ][:5],
            "strongest_categories": sorted(
                categories, key=lambda row: row["first_accuracy"], reverse=True
            )[:5],
            "missed_twice": missed,
        }

    def _categories(self) -> list[dict[str, Any]]:
        first_ids = select(func.min(AnswerAttempt.id)).group_by(AnswerAttempt.question_id)
        rows = self.db.execute(
            select(
                Category.name,
                func.count(distinct(AnswerAttempt.question_id)),
                func.count(AnswerAttempt.id),
                func.sum(case((AnswerAttempt.correct.is_(True), 1), else_=0)),
                func.avg(case((AnswerAttempt.correct.is_(True), 1.0), else_=0.0)),
                func.avg(
                    case(
                        (
                            AnswerAttempt.id.in_(first_ids),
                            case((AnswerAttempt.correct.is_(True), 1.0), else_=0.0),
                        ),
                        else_=None,
                    )
                ),
            )
            .join(Question, Question.category_id == Category.id)
            .join(AnswerAttempt, AnswerAttempt.question_id == Question.id)
            .group_by(Category.id, Category.name)
        ).all()
        values = [
            {
                "category": row[0],
                "questions_attempted": row[1],
                "attempts": row[2],
                "correct": row[3] or 0,
                "incorrect": row[2] - (row[3] or 0),
                "overall_accuracy": round((row[4] or 0) * 100, 1),
                "first_accuracy": round((row[5] or 0) * 100, 1),
            }
            for row in rows
        ]
        return sorted(values, key=lambda row: row["first_accuracy"])

    def _missed_twice(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(
                Question.id,
                Question.text,
                Category.name,
                func.count(AnswerAttempt.id),
                func.max(AnswerAttempt.answered_at),
            )
            .join(Category, Category.id == Question.category_id)
            .join(AnswerAttempt, AnswerAttempt.question_id == Question.id)
            .where(AnswerAttempt.correct.is_(False))
            .group_by(Question.id, Question.text, Category.name)
            .having(func.count(AnswerAttempt.id) >= 2)
            .order_by(func.count(AnswerAttempt.id).desc())
        ).all()
        return [
            {
                "question_id": row[0],
                "question": row[1],
                "category": row[2],
                "incorrect_attempts": row[3],
                "last_attempt": row[4],
            }
            for row in rows
        ]
