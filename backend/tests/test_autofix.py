from types import SimpleNamespace

from app.review.autofix import Suggestion, SuggestionEngine


def _suggestion(**overrides) -> Suggestion:
    values = {
        "id": "fix-1",
        "issue_id": "issue-1",
        "rule_id": "period-spacing",
        "original_text": "Wrong.Text",
        "suggested_text": "Wrong. Text",
        "line_start": 2,
        "line_end": 2,
        "confidence": 99,
        "category": "format",
        "fix_type": "safe",
    }
    values.update(overrides)
    return Suggestion(**values)


def test_apply_replaces_only_the_exact_excerpt_and_preserves_context() -> None:
    engine = SuggestionEngine()
    result = engine.apply_suggestion(
        "Title\nPrefix Wrong.Text suffix\nEnd",
        _suggestion(),
    )
    assert result.success
    assert result.patched_text == "Title\nPrefix Wrong. Text suffix\nEnd"


def test_apply_rejects_stale_or_ambiguous_source() -> None:
    engine = SuggestionEngine()
    stale = engine.apply_suggestion("Title\nAlready fixed.\n", _suggestion())
    assert not stale.success
    assert "changed after preview" in stale.error

    ambiguous = engine.apply_suggestion(
        "Wrong.Text\nWrong.Text",
        _suggestion(line_start=3, line_end=3),
    )
    assert not ambiguous.success
    assert "ambiguous" in ambiguous.error


def test_revert_restores_exact_previous_text() -> None:
    engine = SuggestionEngine()
    suggestion = _suggestion()
    applied = engine.apply_suggestion("A\nWrong.Text\nB", suggestion)
    suggestion.applied = True
    reverted = engine.revert_suggestion(applied.patched_text, suggestion)
    assert reverted.success
    assert reverted.patched_text == "A\nWrong.Text\nB"


def test_bulk_resolves_overlapping_suggestions_by_confidence() -> None:
    engine = SuggestionEngine()
    winner = _suggestion(id="winner", confidence=99)
    blocked = _suggestion(
        id="blocked",
        original_text="Wrong.Text",
        suggested_text="Different text",
        confidence=70,
        fix_type="ai",
    )
    patched, applied, results = engine.apply_suggestions_bulk(
        "A\nWrong.Text\nB",
        [blocked, winner],
    )
    assert patched == "A\nWrong. Text\nB"
    assert [item.id for item in applied] == ["winner"]
    assert any(not result.success and "Conflict" in result.error for result in results)


def test_generated_suggestion_id_is_stable_for_preview_and_apply() -> None:
    engine = SuggestionEngine()
    evidence = SimpleNamespace(excerpt="Wrong.Text", line_start=1, line_end=1)
    issue = SimpleNamespace(
        id="issue-1",
        rule_id="period-spacing",
        severity="low",
        message="Missing space",
        recommendation="Add a space",
        confidence=99,
        category="format",
        autofix_allowed=True,
        evidence=evidence,
    )
    first = engine.generate_suggestions("Wrong.Text", [issue], "session-1")
    second = engine.generate_suggestions("Wrong.Text", [issue], "session-1")
    assert first[0].id == second[0].id

def test_fully_qualified_rule_id_generates_suggestion() -> None:
    engine = SuggestionEngine()
    evidence = SimpleNamespace(excerpt="We recieve the result.", line_start=1, line_end=1)
    issue = SimpleNamespace(
        id="issue-2",
        rule_id="writing.spelling",
        severity="low",
        message="Spelling error",
        recommendation="Use receive",
        confidence=95,
        category="writing",
        autofix_allowed=True,
        evidence=evidence,
    )

    suggestions = engine.generate_suggestions("We recieve the result.", [issue], "session-2")

    assert len(suggestions) == 1
    assert suggestions[0].suggested_text == "We receive the result."
    assert suggestions[0].fix_type == "ai"
