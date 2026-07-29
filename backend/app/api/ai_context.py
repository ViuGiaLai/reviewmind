from __future__ import annotations

from typing import Any


def build_verified_review_context(
    session: dict[str, Any] | None,
    issues: list[dict[str, Any]],
) -> str:
    """Build bounded assistant context exclusively from server-owned records."""
    if not session:
        return ""
    lines = [
        f"Document: {session.get('filename', 'document')}",
        f"Profile: {session.get('profile_id', '')}",
        f"Score: {session.get('score', 0)}/100",
        f"Summary: {session.get('summary', '')}",
        "Top findings:",
    ]
    for issue in issues[:12]:
        lines.append(
            f"- [{issue.get('severity', 'low')}] {issue.get('message', '')} "
            f"Recommendation: {issue.get('recommendation', '')}"
        )
    return "\n".join(lines)
