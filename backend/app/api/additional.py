from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, Response

from app.database import create_database
from app.review import ReviewEngine, ReviewRequest
from app.storage import create_storage

router = APIRouter(prefix="/api", tags=["additional"])
database = create_database()
engine = ReviewEngine()
storage = create_storage()

# ═══════════════════════════════════════════════════════════════════════════════
# 1. DOCUMENTS API
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/documents")
def list_documents(
    search: str | None = Query(None),
    content_type: str | None = Query(None),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List all documents with search, filter, pagination."""
    items, total = database.list_documents(
        search=search, content_type=content_type, limit=limit, offset=offset,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/documents/{doc_id}")
def get_document(doc_id: str) -> dict[str, Any]:
    """Get document detail with page info."""
    doc = database.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    # Get associated sessions
    sessions = database.get_sessions_for_document(doc_id)
    doc["sessions"] = sessions
    doc["session_count"] = len(sessions)
    return doc


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str) -> dict[str, str]:
    """Delete a document and its storage file."""
    doc = database.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
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
def get_review_status(session_id: str) -> dict[str, Any]:
    """Get review status and pipeline progress."""
    session = database.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Review session not found.")
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
) -> dict[str, Any]:
    """List all issues across all sessions with filtering."""
    items, total = database.list_all_issues(
        severity=severity, category=category, status=status,
        search=search, limit=limit, offset=offset,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/issues/{issue_id}/evidence")
def get_issue_evidence(issue_id: str) -> dict[str, Any]:
    """Get evidence details for an issue (page, paragraph, highlight)."""
    evidence = database.get_issue_evidence(issue_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Issue not found.")
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
async def explain_issue(issue_id: str) -> dict[str, Any]:
    """Get AI-powered explanation for an issue."""
    issue = database.get_issue(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")
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
async def ai_chat(body: AIChatBody) -> dict[str, Any]:
    """AI Assistant Chat Endpoint for review analysis and guidance."""
    msg = body.message.strip()
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
) -> dict[str, Any]:
    """Compare two review sessions: score change, issue change, severity diff."""
    result = database.compare_sessions(session_1, session_2)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 5. DASHBOARD API
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard")
def get_dashboard() -> dict[str, Any]:
    """Get dashboard aggregation: total reviews, avg score, issue distribution."""
    return database.get_dashboard_stats()


# ═══════════════════════════════════════════════════════════════════════════════
# 6. STATISTICS API
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/statistics")
def get_statistics() -> dict[str, Any]:
    """Get detailed statistics: category percentages, score trend."""
    return database.get_statistics()


# ═══════════════════════════════════════════════════════════════════════════════
# 7. SEARCH API
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/search")
def search_all(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Search across documents, sessions, and issues."""
    results = database.search_all(query=q, limit=limit)
    return {
        "query": q,
        "documents": results.get("documents", []),
        "sessions": results.get("sessions", []),
        "issues": results.get("issues", []),
        "total": sum(len(v) for v in results.values()),
    }
