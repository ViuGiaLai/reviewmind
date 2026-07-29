from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.auth import get_current_user_id, require_resource_owner
from app.database import create_database
from app.review.autofix import Suggestion, SuggestionEngine
from app.review.autofix.transaction import text_hash
from app.security import audit_log
from app.operations import metrics

router = APIRouter(prefix="/api/sessions/{session_id}/autofix", tags=["autofix"])
engine = SuggestionEngine()
database = create_database()


# ─── Helper ────────────────────────────────────────────────────────────────────

def _get_session(session_id: str, user_id: str | None = None) -> dict[str, Any]:
    return require_resource_owner(database.get_session(session_id), user_id, "Session not found.")



def _get_issues(session_id: str) -> list[dict[str, Any]]:
    issues, _ = database.list_issues(session_id=session_id, limit=500)
    return issues


def _suggestion_to_dict(s: Suggestion) -> dict[str, Any]:
    return {
        "id": s.id,
        "issue_id": s.issue_id,
        "rule_id": s.rule_id,
        "severity": s.severity,
        "message": s.message,
        "original_text": s.original_text,
        "suggested_text": s.suggested_text,
        "line_start": s.line_start,
        "line_end": s.line_end,
        "confidence": s.confidence,
        "category": s.category,
        "fix_type": s.fix_type,
        "applied": s.applied,
        "applied_at": s.applied_at,
        "reverted_at": s.reverted_at,
    }


def _get_document_text(session: dict[str, Any]) -> str | None:
    """Try to retrieve the original document text from storage."""
    doc_id = session.get("document_id")
    if not doc_id:
        return None
    doc = require_resource_owner(database.get_document(doc_id), session.get("user_id"), "Document not found.")
    try:
        from app.storage import create_storage
        storage = create_storage()
        content = storage.read(doc["storage_path"])
        if content:
            # Try to decode as text
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError:
                return content.decode("latin-1")
    except Exception:
        return None
    return None


def _get_current_document_text(session: dict[str, Any]) -> str | None:
    """Return the latest snapshot, falling back to the immutable source document."""
    history = database.get_autofix_history(session["id"])
    if history:
        latest = history[0]
        if latest.get("reverted_at") and latest.get("reverted_document"):
            return latest["reverted_document"]
        if latest.get("patched_document"):
            return latest["patched_document"]
    return _get_document_text(session)

def _import_issues_as_objects(issues: list[dict[str, Any]]) -> list[Any]:
    """Convert dict issues to lightweight named-tuple-like objects for the suggestion engine."""
    from dataclasses import dataclass

    @dataclass
    class _EvidenceRef:
        line_start: int
        line_end: int
        excerpt: str
        location: str

    @dataclass
    class _IssueObj:
        id: str
        issue_id: str
        rule_id: str
        severity: str
        message: str
        recommendation: str
        category: str
        confidence: int
        autofix_allowed: int
        evidence_line_start: int
        evidence_line_end: int
        evidence: _EvidenceRef

    return [
        _IssueObj(
            id=i.get("id", ""),
            issue_id=i.get("issue_id", ""),
            rule_id=i.get("rule_id", ""),
            severity=i.get("severity", "low"),
            message=i.get("message", ""),
            recommendation=i.get("recommendation", ""),
            category=i.get("category", ""),
            confidence=i.get("confidence", 50),
            autofix_allowed=i.get("autofix_allowed", 0),
            evidence_line_start=i.get("evidence_line_start", 1),
            evidence_line_end=i.get("evidence_line_end", 1),
            evidence=_EvidenceRef(
                line_start=i.get("evidence_line_start", 1),
                line_end=i.get("evidence_line_end", 1),
                excerpt=i.get("evidence_excerpt", ""),
                location=i.get("evidence_location", ""),
            ),
        )
        for i in issues
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. GENERATE SUGGESTIONS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/plan")
def get_fix_plan(
    session_id: str,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Build a categorized plan before any change can be applied."""
    response = list_suggestions(session_id, user_id)
    suggestions = [Suggestion(**item) for item in response["items"]]
    plan = engine.planner.create_plan(suggestions)
    return {
        "session_id": session_id,
        "total": plan.total_issues,
        "safe": plan.safe_fixes,
        "confirmation_required": plan.need_confirmation,
        "manual": plan.manual_only,
        "estimated_seconds": plan.estimated_time_seconds,
        "estimated_success_rate": plan.estimated_success_rate,
        "grouped_by_category": plan.grouped_by_category,
    }

@router.get("/suggestions")
def list_suggestions(
    session_id: str,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Generate and return autofix suggestions for a session."""
    session = _get_session(session_id, user_id)
    issues = _get_issues(session_id)

    # Try to get original document text
    text = _get_document_text(session)
    if not text:
        # Fall back to reconstructing from issues
        text = f"Document: {session.get('filename', 'unknown')}\n\n"
        # Build context from issues' evidence lines
        for issue in issues[:20]:
            if issue.get("evidence_excerpt"):
                text += issue["evidence_excerpt"] + "\n"

    issue_objects = _import_issues_as_objects(issues)
    suggestions = engine.generate_suggestions(text, issue_objects, session_id)

    # Check existing applied suggestions from DB
    existing_applied = database.get_applied_suggestions(session_id)
    applied_map = {s["suggestion_id"]: s for s in existing_applied}

    for s in suggestions:
        if s.id in applied_map:
            s.applied = True
            s.applied_at = applied_map[s.id].get("applied_at")
            if applied_map[s.id].get("reverted_at"):
                s.reverted_at = applied_map[s.id]["reverted_at"]
                s.applied = False

    return {
        "session_id": session_id,
        "total": len(suggestions),
        "items": [_suggestion_to_dict(s) for s in suggestions],
        "applied_count": sum(1 for s in suggestions if s.applied),
    }


@router.get("/suggestions/{suggestion_id}")
def get_suggestion_detail(
    session_id: str,
    suggestion_id: str,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get detail of a specific suggestion with diff output."""
    suggestions_resp = list_suggestions(session_id, user_id)
    for s in suggestions_resp["items"]:
        if s["id"] == suggestion_id:
            diff = engine.generate_diff(s["original_text"], s["suggested_text"])
            s["diff"] = [asdict(d) for d in diff]
            return s
    raise HTTPException(status_code=404, detail="Suggestion not found.")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. APPLY SUGGESTION
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/apply/{suggestion_id}")
def apply_suggestion(
    session_id: str,
    suggestion_id: str,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Apply a single autofix suggestion."""
    suggestions_resp = list_suggestions(session_id, user_id)
    target = None
    for s in suggestions_resp["items"]:
        if s["id"] == suggestion_id:
            target = s
            break

    if not target:
        raise HTTPException(status_code=404, detail="Suggestion not found.")

    if target["applied"]:
        raise HTTPException(status_code=400, detail="Suggestion already applied.")

    # Reconstruct Suggestion object
    suggestion = Suggestion(
        id=target["id"],
        issue_id=target["issue_id"],
        rule_id=target["rule_id"],
        severity=target["severity"],
        message=target["message"],
        original_text=target["original_text"],
        suggested_text=target["suggested_text"],
        line_start=target["line_start"],
        line_end=target["line_end"],
        confidence=target["confidence"],
        category=target["category"],
        fix_type=target["fix_type"],
    )

    # Get text and apply
    session = _get_session(session_id, user_id)
    text = _get_current_document_text(session) or ""
    if not text:
        raise HTTPException(status_code=400, detail="No source document text available for autofix.")

    result = engine.apply_suggestion(text, suggestion)
    if not result.success:
        raise HTTPException(status_code=422, detail=result.error or "Failed to apply suggestion.")

    # Save to database
    action_id = database.save_autofix_action(
        session_id=session_id,
        suggestion_id=suggestion_id,
        issue_id=suggestion.issue_id,
        rule_id=suggestion.rule_id,
        action_type="apply",
        original_text=suggestion.original_text,
        patched_text=suggestion.suggested_text,
        line_start=suggestion.line_start,
        line_end=suggestion.line_end,
        patched_document=result.patched_text,
    )

    metrics.increment("reviewmind_autofix_total", outcome="success", mode="single")
    audit_log.record(
        actor_id=user_id or "anonymous", action="autofix.apply",
        resource_type="session", resource_id=session_id,
        metadata={"suggestion_id": suggestion_id, "rule_id": suggestion.rule_id},
    )

    return {
        "action_id": action_id,
        "suggestion_id": suggestion_id,
        "status": "applied",
        "changes": result.changes,
        "document_hash": text_hash(result.patched_text),
        "verification": "passed",
    }


@router.post("/revert/{suggestion_id}")
def revert_suggestion(
    session_id: str,
    suggestion_id: str,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Revert a previously applied suggestion."""
    session = _get_session(session_id, user_id)  # Verify ownership + fetch session
    # Check existing applied suggestions
    existing = database.get_applied_suggestions(session_id)
    target = None
    for s in existing:
        if s["suggestion_id"] == suggestion_id and not s.get("reverted_at"):
            target = s
            break

    if not target:
        raise HTTPException(status_code=404, detail="Applied suggestion not found or already reverted.")

    if existing and existing[0]["suggestion_id"] != suggestion_id:
        raise HTTPException(
            status_code=409,
            detail="Undo must follow reverse application order to preserve version history.",
        )

    # Reconstruct suggestion
    suggestion = Suggestion(
        id=target["suggestion_id"],
        issue_id=target["issue_id"],
        rule_id=target["rule_id"],
        severity="low",
        message="",
        original_text=target["original_text"],
        suggested_text=target["patched_text"],
        line_start=target["line_start"],
        line_end=target["line_end"],
        confidence=50,
        category="",
        applied=True,
        applied_at=target.get("applied_at"),
    )

    text = _get_current_document_text(session) or ""
    if not text:
        # Try to use the patched document stored in DB
        text = target.get("patched_document", "")
    if not text:
        raise HTTPException(status_code=400, detail="No source text available for revert.")

    result = engine.revert_suggestion(text, suggestion)
    if not result.success:
        raise HTTPException(status_code=422, detail=result.error or "Failed to revert suggestion.")

    # Update database
    database.revert_autofix_action(target["id"], result.patched_text)
    audit_log.record(
        actor_id=user_id or "anonymous", action="autofix.revert",
        resource_type="session", resource_id=session_id,
        metadata={"suggestion_id": suggestion_id},
    )

    return {
        "action_id": target["id"],
        "suggestion_id": suggestion_id,
        "status": "reverted",
    }


@router.post("/apply-bulk")
def apply_suggestions_bulk(
    session_id: str,
    body: dict[str, Any],
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Apply multiple suggestions at once."""
    suggestion_ids: list[str] = body.get("suggestion_ids", [])
    if not suggestion_ids:
        raise HTTPException(status_code=400, detail="No suggestion IDs provided.")

    suggestions_resp = list_suggestions(session_id, user_id)
    targets = [s for s in suggestions_resp["items"] if s["id"] in suggestion_ids and not s["applied"]]

    if not targets:
        raise HTTPException(status_code=404, detail="No applicable suggestions found.")

    suggestion_objs = [
        Suggestion(
            id=t["id"],
            issue_id=t["issue_id"],
            rule_id=t["rule_id"],
            severity=t["severity"],
            message=t["message"],
            original_text=t["original_text"],
            suggested_text=t["suggested_text"],
            line_start=t["line_start"],
            line_end=t["line_end"],
            confidence=t["confidence"],
            category=t["category"],
            fix_type=t["fix_type"],
        )
        for t in targets
    ]

    session = _get_session(session_id, user_id)
    text = _get_current_document_text(session) or ""
    if not text:
        raise HTTPException(status_code=400, detail="No source document text available for autofix.")

    patched_text, applied, results = engine.apply_suggestions_bulk(text, suggestion_objs)

    # Save all applied suggestions
    for s in applied:
        database.save_autofix_action(
            session_id=session_id,
            suggestion_id=s.id,
            issue_id=s.issue_id,
            rule_id=s.rule_id,
            action_type="apply",
            original_text=s.original_text,
            patched_text=s.suggested_text,
            line_start=s.line_start,
            line_end=s.line_end,
            patched_document=patched_text,
        )

    metrics.increment("reviewmind_autofix_total", value=len(applied), outcome="success", mode="bulk")
    metrics.increment("reviewmind_autofix_total", value=sum(1 for result in results if not result.success), outcome="failure", mode="bulk")
    audit_log.record(
        actor_id=user_id or "anonymous", action="autofix.apply_bulk",
        resource_type="session", resource_id=session_id,
        metadata={"applied_count": len(applied)},
    )

    return {
        "session_id": session_id,
        "applied": len(applied),
        "failed": sum(1 for r in results if not r.success),
        "errors": [r.error for r in results if not r.success],
        "document_hash": text_hash(patched_text),
        "verification": "passed" if applied else "no_changes",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 3. VERSION HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/history")
def get_autofix_history(
    session_id: str,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get the autofix action history for a session."""
    _get_session(session_id, user_id)  # verify session exists + ownership
    actions = database.get_autofix_history(session_id)
    return {
        "session_id": session_id,
        "total": len(actions),
        "items": actions,
    }


@router.get("/diff")
def get_full_diff(
    session_id: str,
    user_id: str | None = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get the cumulative diff of all applied suggestions."""
    _get_session(session_id, user_id)
    actions = database.get_autofix_history(session_id)

    # Reconstruct the diff from applied actions
    diffs = []
    for action in actions:
        if action.get("action_type") == "apply":
            diffs.append({
                "action_id": action["id"],
                "suggestion_id": action["suggestion_id"],
                "rule_id": action.get("rule_id", ""),
                "line_start": action.get("line_start", 0),
                "line_end": action.get("line_end", 0),
                "action": "apply",
                "original": action.get("original_text", ""),
                "patched": action.get("patched_text", ""),
                "applied_at": action.get("created_at", ""),
            })
        # Check if reverted (reverted_at is set)
        if action.get("reverted_at"):
            diffs.append({
                "action_id": action["id"],
                "suggestion_id": action["suggestion_id"],
                "rule_id": action.get("rule_id", ""),
                "action": "revert",
                "original": action.get("patched_text", ""),
                "patched": action.get("original_text", ""),
                "reverted_at": action.get("reverted_at", ""),
            })

    return {
        "session_id": session_id,
        "total_changes": len(diffs),
        "applied_count": sum(1 for d in diffs if d["action"] == "apply"),
        "reverted_count": sum(1 for d in diffs if d["action"] == "revert"),
        "diffs": diffs,
    }
