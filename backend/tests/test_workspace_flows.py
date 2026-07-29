from app.api.ai_context import build_verified_review_context
from app.database.postgres_adapter import PostgresAdapter


def test_ai_context_uses_only_verified_server_records() -> None:
    session = {
        "filename": "trusted.docx",
        "profile_id": "academic",
        "score": 72,
        "summary": "Trusted server summary",
    }
    issues = [{
        "severity": "high",
        "message": "Trusted finding",
        "recommendation": "Trusted recommendation",
    }]

    context = build_verified_review_context(session, issues)

    assert "trusted.docx" in context
    assert "Trusted finding" in context
    assert "Trusted recommendation" in context
    assert "forged.docx" not in context


def test_knowledge_pack_catalog_exposes_execution_metadata() -> None:
    packs = PostgresAdapter("postgresql://unused").list_packs()
    ieee = next(pack for pack in packs if pack["id"] == "ieee")

    assert ieee["version"]
    assert ieee["categories"] == ["citation"]
    assert ieee["required_packs"] == ["academic-base"]
    assert ieee["capability_count"] >= 1