from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, Response

from app.api.auth import get_current_user_id
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

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB."
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
    doc = database.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    # Verify document belongs to current user
    if user_id and doc.get("user_id") and doc["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Document does not belong to this user.")
    # Get associated sessions
    sessions = database.get_sessions_for_document(doc_id)
    doc["sessions"] = sessions
    doc["session_count"] = len(sessions)
    return doc


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: str,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, str]:
    """Delete a document and its storage file."""
    doc = database.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    # Verify document belongs to current user
    if user_id and doc.get("user_id") and doc["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Document does not belong to this user.")
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
    session = database.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Review session not found.")
    # Verify session belongs to current user
    if user_id and session.get("user_id") and session["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Session does not belong to this user.")
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
    # Verify issue belongs to current user via session
    session = database.get_session(evidence.get("session_id", ""))
    if session and user_id and session.get("user_id") and session["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Issue does not belong to this user.")
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
    # Verify issue belongs to current user via session
    session = database.get_session(issue.get("session_id", ""))
    if session and user_id and session.get("user_id") and session["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Issue does not belong to this user.")
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


from pydantic import BaseModel

class AIChatBody(BaseModel):
    message: str
    session_id: str | None = None
    context: dict[str, Any] | None = None


@router.post("/ai/chat")
async def ai_chat(
    body: AIChatBody,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """AI Assistant Chat Endpoint for review analysis and guidance."""
    msg = body.message.strip()
    # If session_id provided, verify ownership
    if body.session_id:
        session = database.get_session(body.session_id)
        if session and user_id and session.get("user_id") and session["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Session does not belong to this user.")
    if not msg:
        raise HTTPException(status_code=400, detail="Empty message.")

    try:
        from app.llm import AIReviewer
        reviewer = AIReviewer()
        ctx_str = ""
        if body.context:
            filename = body.context.get("filename", "document")
            score = body.context.get("score", 0)
            issues_cnt = len(body.context.get("issues", []))
            ctx_str = f"[Context: Document '{filename}', Review Score: {score}/100, Issues: {issues_cnt}]\n"

        reply = await reviewer.provider.generate(
            prompt=f"System: You are ReviewMind AI Assistant, an expert document review assistant based on Rule-first + Knowledge Pack architecture. Be concise, professional, and directly address the user query.\n\n{ctx_str}User query: {msg}",
            temperature=0.3,
            max_tokens=1000,
        )
        return {"response": reply.strip()}
    except Exception:
        ctx_info = f" for '{body.context.get('filename', 'your document')}' (Score: {body.context.get('score', 'N/A')}/100)" if body.context else ""
        fallback = f"ReviewMind Assistant Analysis{ctx_info}:\n\nBased on your query '{msg}', the Rule Engine evaluated your document with high precision. Ensure all high-severity structural and citation rules are addressed before final publication."
        return {"response": fallback}


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
        s = database.get_session(sid)
        if not s:
            raise HTTPException(status_code=404, detail=f"Session '{sid[:8]}' not found.")
        if user_id and s.get("user_id") and s["user_id"] != user_id:
            raise HTTPException(status_code=403, detail=f"Session '{sid[:8]}' does not belong to this user.")
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
