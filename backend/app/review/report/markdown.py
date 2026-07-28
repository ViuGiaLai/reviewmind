from __future__ import annotations

from ..models import Issue


def render_markdown(profile_id: str, score: int, issues: list[Issue]) -> str:
    lines = [f"# ReviewMind report", "", f"Profile: **{profile_id}**", f"Overall score: **{score}/100**", "", "## Issues"]
    if not issues:
        lines.append("No issues were detected by the enabled deterministic rules.")
    for issue in issues:
        lines.extend([f"### {issue.severity.value.upper()} — {issue.message}", f"- Category: {issue.category}", f"- Evidence: {issue.evidence.excerpt}", f"- Recommendation: {issue.recommendation}"])
    return "\n".join(lines)
