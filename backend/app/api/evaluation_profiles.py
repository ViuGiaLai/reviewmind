from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.auth import get_current_user_id, require_resource_owner
from app.database import create_database
from app.review import ReviewEngine
from app.security import audit_log


router = APIRouter(prefix="/api/evaluation-profiles", tags=["evaluation-profiles"])
database = create_database()
engine = ReviewEngine()


class EvaluationProfileBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    base_profile_id: str = Field(default="academic", min_length=1, max_length=80)
    document_types: list[str] = Field(default_factory=list, max_length=20)
    knowledge_pack_ids: list[str] = Field(default_factory=list, max_length=30)
    reference_template_id: str | None = None
    enabled_categories: list[str] = Field(default_factory=list, max_length=30)
    ai_review_enabled: bool = True
    auto_fix_enabled: bool = False
    scoring_profile: Literal["weighted", "equal"] = "weighted"
    language: Literal["vi", "en"] = "vi"
    review_mode: Literal["strict", "standard", "relaxed"] = "standard"
    visibility: Literal["private"] = "private"


def _require_authenticated(user_id: str | None) -> str:
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required for evaluation profiles.",
        )
    return user_id


def _public(profile: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in profile.items() if key != "user_id"}


def _validate_profile(body: EvaluationProfileBody, user_id: str) -> dict[str, Any]:
    try:
        base = engine.profiles.load(body.base_profile_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    categories = list(dict.fromkeys(body.enabled_categories or base.categories))
    unknown_categories = sorted(set(categories) - set(base.categories))
    if unknown_categories:
        raise HTTPException(
            status_code=422,
            detail=f"Categories are not supported by the base profile: {', '.join(unknown_categories)}",
        )

    valid_pack_ids = {pack["id"] for pack in database.list_packs()}
    unknown_packs = sorted(set(body.knowledge_pack_ids) - valid_pack_ids)
    if unknown_packs:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown knowledge packs: {', '.join(unknown_packs)}",
        )

    if body.reference_template_id:
        require_resource_owner(
            database.get_reference_template(body.reference_template_id),
            user_id,
            "Reference template not found.",
        )

    data = body.model_dump()
    data["name"] = body.name.strip()
    data["description"] = body.description.strip()
    data["document_types"] = list(dict.fromkeys(item.strip() for item in body.document_types if item.strip()))
    data["knowledge_pack_ids"] = list(dict.fromkeys(body.knowledge_pack_ids))
    data["enabled_categories"] = categories
    return data


@router.get("")
def list_evaluation_profiles(
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    owner_id = _require_authenticated(user_id)
    items = database.list_evaluation_profiles(owner_id)
    return {"items": [_public(item) for item in items], "total": len(items)}


@router.get("/options")
def get_evaluation_profile_options(
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    owner_id = _require_authenticated(user_id)
    builtins = []
    for item in engine.profiles.available():
        profile = engine.profiles.load(item["id"])
        builtins.append(
            {
                "id": profile.id,
                "name": profile.name,
                "document_types": profile.document_types,
                "categories": profile.categories,
                "weights": profile.weights,
            }
        )
    return {
        "base_profiles": builtins,
        "knowledge_packs": database.list_packs(),
        "templates": [
            {"id": item["id"], "original_name": item["original_name"]}
            for item in database.list_reference_templates(owner_id)
        ],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_evaluation_profile(
    body: EvaluationProfileBody,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    owner_id = _require_authenticated(user_id)
    data = _validate_profile(body, owner_id)
    profile_id = database.create_evaluation_profile(owner_id, data)
    audit_log.record(
        actor_id=owner_id,
        action="evaluation_profile.created",
        resource_type="evaluation_profile",
        resource_id=profile_id,
    )
    saved = database.get_evaluation_profile(profile_id)
    return _public(saved) if saved else {"id": profile_id, **data}


@router.get("/{profile_id}")
def get_evaluation_profile(
    profile_id: str,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    owner_id = _require_authenticated(user_id)
    profile = require_resource_owner(
        database.get_evaluation_profile(profile_id),
        owner_id,
        "Evaluation profile not found.",
    )
    return _public(profile)


@router.patch("/{profile_id}")
def update_evaluation_profile(
    profile_id: str,
    body: EvaluationProfileBody,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    owner_id = _require_authenticated(user_id)
    require_resource_owner(
        database.get_evaluation_profile(profile_id),
        owner_id,
        "Evaluation profile not found.",
    )
    data = _validate_profile(body, owner_id)
    database.update_evaluation_profile(profile_id, owner_id, data)
    audit_log.record(
        actor_id=owner_id,
        action="evaluation_profile.updated",
        resource_type="evaluation_profile",
        resource_id=profile_id,
    )
    saved = database.get_evaluation_profile(profile_id)
    return _public(saved) if saved else {"id": profile_id, **data}


@router.delete("/{profile_id}")
def delete_evaluation_profile(
    profile_id: str,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, str]:
    owner_id = _require_authenticated(user_id)
    if not database.delete_evaluation_profile(profile_id, owner_id):
        raise HTTPException(status_code=404, detail="Evaluation profile not found.")
    audit_log.record(
        actor_id=owner_id,
        action="evaluation_profile.deleted",
        resource_type="evaluation_profile",
        resource_id=profile_id,
    )
    return {"status": "deleted"}
