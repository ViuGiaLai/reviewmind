from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.auth import get_current_user_id, require_resource_owner
from app.api.upload_utils import read_upload_limited
from app.config import settings
from app.database import create_database
from app.review.reference_templates import ReferenceTemplateEngine
from app.storage import create_storage


router = APIRouter(prefix="/api/templates", tags=["reference-templates"])
database = create_database()
storage = create_storage()
template_engine = ReferenceTemplateEngine()
MAX_TEMPLATE_SIZE = 25 * 1024 * 1024


def _public(template: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in template.items()
        if key not in {"storage_path", "user_id"}
    }


@router.post("/upload")
async def upload_reference_template(
    file: UploadFile = File(...),
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    if not file.filename or Path(file.filename).suffix.casefold() != ".docx":
        raise HTTPException(status_code=400, detail="Reference templates must be DOCX files.")
    content = await read_upload_limited(
        file, max_bytes=MAX_TEMPLATE_SIZE, chunk_size=settings.app.upload_chunk_size
    )
    if not content:
        raise HTTPException(status_code=400, detail="Empty template file.")

    try:
        analysis = template_engine.learn(content, file.filename)
    except (ValueError, KeyError) as error:
        raise HTTPException(status_code=422, detail=f"Unable to learn this DOCX template: {error}") from error

    storage_path, _ = storage.save(content, file.filename)
    try:
        template_id = database.save_reference_template(
            original_name=file.filename,
            size=len(content),
            storage_path=storage_path,
            analysis=analysis,
            user_id=user_id,
        )
    except Exception:
        storage.delete(storage_path)
        raise

    saved = database.get_reference_template(template_id)
    return _public(saved or {"id": template_id, "original_name": file.filename, "analysis": analysis})


@router.get("")
def list_reference_templates(
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    items = database.list_reference_templates(user_id=user_id)
    return {"items": [_public(item) for item in items], "total": len(items)}


@router.get("/{template_id}")
def get_reference_template(
    template_id: str,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    item = require_resource_owner(
        database.get_reference_template(template_id), user_id, "Reference template not found."
    )
    return _public(item)


@router.delete("/{template_id}")
def delete_reference_template(
    template_id: str,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, str]:
    item = require_resource_owner(
        database.get_reference_template(template_id), user_id, "Reference template not found."
    )
    database.delete_reference_template(template_id)
    try:
        storage.delete(item.get("storage_path", ""))
    except Exception:
        pass
    return {"status": "deleted"}
