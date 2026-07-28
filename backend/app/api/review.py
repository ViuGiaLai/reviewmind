from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.review import ReviewEngine, ReviewRequest

router = APIRouter(prefix="/api", tags=["review"])
engine = ReviewEngine()


class ReviewBody(BaseModel):
    text: str = Field(min_length=1, max_length=2_000_000)
    filename: str = "document.md"
    content_type: str = "text/markdown"
    profile_id: str = "academic"
    pack_ids: list[str] = []
    enabled_categories: list[str] | None = None


@router.get("/profiles")
def profiles() -> list[dict[str, str]]:
    return engine.profiles.available()


@router.post("/reviews")
def review(body: ReviewBody) -> dict:
    try:
        return asdict(engine.review(ReviewRequest(**body.model_dump())))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
