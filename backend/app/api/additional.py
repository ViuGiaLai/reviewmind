from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, Response

from app.api.auth import get_current_user_id, require_resource_owner
from app.api.upload_utils import read_upload_limited
from app.api.ai_context import build_verified_review_context
from app.config import settings
from app.database import create_database
from app.storage import create_storage

router = APIRouter(prefix="/api", tags=["additional"])
database = create_database()
storage = create_storage()

MAX_FILE_SIZE = settings.app.max_file_size
ALLOWED_MIME_TYPES: dict[str, str] = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
    ".tex": "text/x-tex",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
}
ALLOWED_EXTENSIONS = set(ALLOWED_MIME_TYPES.keys())

# ═══════════════════════════════════════════════════════════════════════════════
# 0. DOCUMENT UPLOAD (dedicated, no review)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """
    Upload a file to storage and save its metadata.
    Returns immediately with the document_id — no review is triggered.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    suffix = Path(file.filename).suffix.casefold()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await read_upload_limited(
        file, max_bytes=MAX_FILE_SIZE, chunk_size=settings.app.upload_chunk_size
    )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file.")

    content_type = ALLOWED_MIME_TYPES.get(suffix, file.content_type or "application/octet-stream")

    # Save to storage
    storage_path, safe_name = storage.save(content, file.filename)

    # Save document record
    doc_id = database.save_document(
        original_name=file.filename,
        content_type=content_type,
        size=len(content),
        storage_path=storage_path,
        user_id=user_id,
    )

    return {
        "document_id": doc_id,
        "filename": file.filename,
        "size": len(content),
        "content_type": content_type,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 1. DOCUMENTS API
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/documents")
def list_documents(
    search: str | None = Query(None),
    content_type: str | None = Query(None),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """List documents for the current user with search, filter, pagination."""
    items, total = database.list_documents(
        search=search, content_type=content_type, limit=limit, offset=offset,
        user_id=user_id,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/documents/{doc_id}")
def get_document(
    doc_id: str,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get document detail with page info."""
    doc = require_resource_owner(database.get_document(doc_id), user_id, "Document not found.")

    # Get associated sessions
    sessions = database.get_sessions_for_document(doc_id, user_id=user_id)
    doc["sessions"] = sessions
    doc["session_count"] = len(sessions)
    return doc


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: str,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, str]:
    """Delete a document and its storage file."""
    doc = require_resource_owner(database.get_document(doc_id), user_id, "Document not found.")

    # Delete from storage
    try:
        storage.delete(doc.get("storage_path", ""))
    except Exception:
        pass  # Best-effort storage cleanup
    # Delete document record (cascades to sessions/issues via FK)
    database.delete_document(doc_id)
    return {"status": "deleted"}


# ═══════════════════════════════════════════════════════════════════════════════
# 2. REVIEW STATUS API
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/reviews/{session_id}")
def get_review_status(
    session_id: str,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get review status and pipeline progress."""
    session = require_resource_owner(database.get_session(session_id), user_id, "Review session not found.")

    issues, _ = database.list_issues(session_id=session_id, limit=500)
    return {
        "id": session["id"],
        "status": session.get("status", "completed"),
        "pipeline_stage": "completed",
        "progress": 100,
        "filename": session.get("filename"),
        "profile_id": session.get("profile_id"),
        "score": session.get("score"),
        "issue_count": len(issues),
        "created_at": session.get("created_at"),
        "estimated_completion": session.get("created_at"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ISSUES API (Global)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/issues")
def list_all_issues(
    severity: str | None = Query(None, pattern=r"^(high|medium|low)$"),
    category: str | None = Query(None),
    status: str | None = Query(None, pattern=r"^(open|resolved|ignored)$"),
    search: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """List issues for the current user across sessions with filtering."""
    items, total = database.list_all_issues(
        severity=severity, category=category, status=status,
        search=search, limit=limit, offset=offset,
        user_id=user_id,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/issues/{issue_id}/evidence")
def get_issue_evidence(
    issue_id: str,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get evidence details for an issue (page, paragraph, highlight)."""
    evidence = database.get_issue_evidence(issue_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Issue not found.")
    require_resource_owner(database.get_session(evidence.get("session_id", "")), user_id, "Issue not found.")

    return {
        "issue_id": evidence["id"],
        "excerpt": evidence.get("evidence_excerpt", ""),
        "line_start": evidence.get("evidence_line_start", 0),
        "line_end": evidence.get("evidence_line_end", 0),
        "location": evidence.get("evidence_location", ""),
        "document": evidence.get("filename", ""),
        "evidence_html": f'<mark class="evidence-highlight" data-lines="{evidence.get("evidence_line_start",0)}-{evidence.get("evidence_line_end",0)}">{evidence.get("evidence_excerpt","")}</mark>',
    }


@router.get("/issues/{issue_id}/explain")
async def explain_issue(
    issue_id: str,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get AI-powered explanation for an issue."""
    issue = database.get_issue(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")
    require_resource_owner(database.get_session(issue.get("session_id", "")), user_id, "Issue not found.")

    try:
        from dataclasses import dataclass
        from app.llm import AIReviewer

        @dataclass
        class _EvidenceRef:
            excerpt: str
        @dataclass
        class _RefIssue:
            category: str
            rule_id: str
            severity: str
            message: str
            recommendation: str
            evidence: _EvidenceRef

        reviewer = AIReviewer()
        explanation = await reviewer.explain_issue(
            issue=_RefIssue(
                category=issue.get("category", ""),
                rule_id=issue.get("rule_id", ""),
                severity=issue.get("severity", "medium"),
                message=issue.get("message", ""),
                recommendation=issue.get("recommendation", ""),
                evidence=_EvidenceRef(excerpt=issue.get("evidence_excerpt", "")),
            ),
            document_excerpt=issue.get("evidence_excerpt", ""),
        )
    except Exception:
        explanation = "AI explanation unavailable. Configure an LLM provider (REVIEWMIND_GEMINI_API_KEY, REVIEWMIND_OPENROUTER_API_KEY, or REVIEWMIND_GITHUB_TOKEN)."
    return {"issue_id": issue_id, "explanation": explanation}


from pydantic import BaseModel, Field

class AIChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None
    context: dict[str, Any] | None = None


@router.post("/ai/chat")
async def ai_chat(
    body: AIChatBody,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """AI Assistant Chat Endpoint for review analysis and guidance."""
    msg = body.message.strip()
    session: dict[str, Any] | None = None
    issues: list[dict[str, Any]] = []
    if body.session_id:
        session = require_resource_owner(
            database.get_session(body.session_id), user_id, "Session not found."
        )
        issues, _ = database.list_issues(session_id=body.session_id, limit=12)

    ctx_str = build_verified_review_context(session, issues)

    try:
        from app.llm import AIReviewer
        reviewer = AIReviewer()
        reply = await reviewer.answer_question(question=msg, document_context=ctx_str)
        return {"response": reply.strip(), "grounded": bool(session)}
    except Exception:
        if session:
            fallback = (
                f"ReviewMind Assistant — {session.get('filename', 'document')} "
                f"({session.get('score', 0)}/100):\n\n"
                "Prioritize open high-severity findings, then verify structural and citation issues "
                "against their evidence before applying any content change."
            )
        else:
            fallback = (
                "Run or select a review first so the assistant can answer from verified findings. "
                "General guidance is available, but it is not document-grounded."
            )
        return {"response": fallback, "grounded": bool(session)}


# ═══════════════════════════════════════════════════════════════════════════════
# 4. HISTORY COMPARE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/history/compare")
def compare_history(
    session_1: str = Query(..., description="First session ID"),
    session_2: str = Query(..., description="Second session ID"),
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Compare two review sessions: score change, issue change, severity diff."""
    # Verify both sessions belong to current user
    for sid in (session_1, session_2):
        require_resource_owner(database.get_session(sid), user_id, f"Session '{sid[:8]}' not found.")

    result = database.compare_sessions(session_1, session_2)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 5. DASHBOARD API
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard")
def get_dashboard(
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get dashboard aggregation scoped to current user."""
    return database.get_dashboard_stats(user_id=user_id)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. STATISTICS API
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/statistics")
def get_statistics(
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get detailed statistics scoped to current user."""
    return database.get_statistics(user_id=user_id)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. SEARCH API
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/search")
def search_all(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Search across documents, sessions, and issues (scoped to current user)."""
    results = database.search_all(query=q, limit=limit, user_id=user_id)
    return {
        "query": q,
        "documents": results.get("documents", []),
        "sessions": results.get("sessions", []),
        "issues": results.get("issues", []),
        "total": sum(len(v) for v in results.values()),
    }
