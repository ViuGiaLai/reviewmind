"""Writing rules: passive voice, readability, hedging, tone, terminology consistency."""

from __future__ import annotations

import re
from typing import Any

from ..models import DocumentModel, Evidence, Issue, Severity
from ..profiles import Profile
from .registry import rule

# ── Patterns ───────────────────────────────────────────────────────────────────

# Passive voice indicators
PASSIVE_PATTERN = re.compile(
    r"\b(?:am|is|are|was|were|be|been|being)\s+(\w+ed|written|known|shown|given|found|"
    r"taken|made|done|said|seen|used|created|developed|established|defined|"
    r"performed|conducted|carried|presented|described|discussed|suggested|"
    r"observed|noted|reported|proposed|required|determined)\b",
    re.I,
)

# Hedging words
HEDGING_WORDS = {
    "maybe", "perhaps", "possibly", "probably", "likely", "unlikely",
    "presumably", "arguably", "apparently", "seemingly",
    "might", "may", "could", "would", "can",
    "somewhat", "rather", "quite", "relatively",
    "suggests", "appears", "seems", "tends",
    "to some extent", "in general", "generally",
}
HEDGING_PATTERN = re.compile(
    r"\b(?:" + "|".join(HEDGING_WORDS) + r")\b", re.I
)

# Weak wording
WEAK_WORDS = {
    "very", "really", "quite", "basically", "actually", "literally",
    "just", "simply", "nicely", "good", "bad", "big", "small",
    "interesting", "important", "significant", "various",
}
WEAK_PATTERN = re.compile(
    r"\b(?:" + "|".join(WEAK_WORDS) + r")\b", re.I
)

# Verbose phrases
VERBOSE_PATTERNS = [
    (re.compile(r"\bin\s+order\s+to\b", re.I), "use 'to' instead of 'in order to'"),
    (re.compile(r"\bdue\s+to\s+the\s+fact\s+that\b", re.I), "use 'because' instead of 'due to the fact that'"),
    (re.compile(r"\bin\s+spite\s+of\s+the\s+fact\s+that\b", re.I), "use 'although' instead of 'in spite of the fact that'"),
    (re.compile(r"\bin\s+the\s+event\s+that\b", re.I), "use 'if' instead of 'in the event that'"),
    (re.compile(r"\bon\s+a\s+\w+\s+basis\b", re.I), "use the adverb directly (e.g., 'daily' instead of 'on a daily basis')"),
    (re.compile(r"\bat\s+this\s+point\s+in\s+time\b", re.I), "use 'now' or 'currently' instead of 'at this point in time'"),
    (re.compile(r"\bin\s+the\s+majority\s+of\s+cases\b", re.I), "use 'usually' or 'typically' instead"),
    (re.compile(r"\ba\s+majority\s+of\b", re.I), "use 'most' instead of 'a majority of'"),
    (re.compile(r"\ba\s+number\s+of\b", re.I), "use 'many' or 'several' instead of 'a number of'"),
    (re.compile(r"\bis\s+able\s+to\b", re.I), "use 'can' instead of 'is able to'"),
    (re.compile(r"\bis\s+capable\s+of\b", re.I), "use 'can' instead of 'is capable of'"),
]

# Repetition indicators
REPETITION_WORDS_PATTERN = re.compile(
    r"\b(however|therefore|moreover|furthermore|nevertheless|consequently|"
    r"additionally|in addition|thus|hence|accordingly)\b",
    re.I,
)

# Contractions (usually not allowed in academic writing)
CONTRACTION_PATTERN = re.compile(
    r"\b(can't|don't|won't|wouldn't|shouldn't|couldn't|isn't|aren't|wasn't|"
    r"weren't|hasn't|haven't|hadn't|doesn't|didn't|it's|that's|there's|"
    r"they're|we're|you're|i'm|i've|they've|we've|i'll|they'll|we'll|"
    r"i'd|they'd|we'd|let's)\b",
    re.I,
)

# ── Grammar & Spelling Patterns ──────────────────────────────────────────────

# Common grammar errors (pattern, description)
COMMON_GRAMMAR_ERRORS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(its|it's)\s+(a|an|the|not|was|is)\b", re.I), "Possible its/it's confusion"),
    (re.compile(r"\byour\s+(a|an|the|not|was|is|were|are)\b", re.I), "Possible your/you're confusion"),
    (re.compile(r"\bthere\s+(a|an|the|not|was|is)\s", re.I), "Possible their/there/they're confusion"),
    (re.compile(r"\b(affect|effect)\s", re.I), "Possible affect/effect confusion"),
    (re.compile(r"\b(complement|compliment)\b", re.I), "Possible complement/compliment confusion"),
    (re.compile(r"\b(principal|principle)\b", re.I), "Possible principal/principle confusion"),
    (re.compile(r"\b(stationary|stationery)\b", re.I), "Possible stationary/stationery confusion"),
    (re.compile(r"\b(than|then)\s+(a|an|the|it|we|they|i|he|she)\b", re.I), "Possible than/then confusion"),
    (re.compile(r"\b(who's|whose)\s", re.I), "Possible who's/whose confusion"),
    (re.compile(r"\bloose\s+(a|an|the|and|but|or)\b", re.I), "Possible loose/lose confusion"),
    (re.compile(r"\b(less|fewer)\s+(people|items|results|studies|papers|participants)", re.I), "Use 'fewer' with countable nouns"),
    (re.compile(r"\b(between|among)\s+(a|an|each|every|one|two)", re.I), "Possible between/among confusion"),
    (re.compile(r"\bmyself\s+(is|am|was|were|will|can|would)\b", re.I), "Overuse of 'myself' (use 'me' or 'I')"),
    (re.compile(r"\b(which|that)\s+(was|is|are|were)\s+(very|really|quite)\b", re.I), "Possible 'which' vs 'that' confusion"),
    (re.compile(r"\b(data|criterion|phenomenon|analysis|hypothesis|thesis|curriculum|memorandum)\s+(is|was)\b", re.I), "Possible subject-verb agreement (these may be plural)"),
    (re.compile(r"\b(datas|criterions|phenomenons|analysis|hypothesises|thesises|curriculums|memorandums)\b", re.I), "Incorrect plural form"),
    (re.compile(r"\b(irregardless)\b", re.I), "'Irregardless' is non-standard. Use 'regardless'"),
    (re.compile(r"\b(alot)\b", re.I), "'Alot' should be 'a lot'"),
    (re.compile(r"\bcould of|would of|should of|might of\b", re.I), "Use 'could have' instead of 'could of'"),
    (re.compile(r"\bsuppose to|use to\b", re.I), "Use 'supposed to' or 'used to'"),
]

# Common typos (word -> correction)
COMMON_TYPOS: dict[str, str] = {
    "accomodate": "accommodate",
    "achive": "achieve",
    "adress": "address",
    "alot": "a lot",
    "apparant": "apparent",
    "appart": "apart",
    "aquire": "acquire",
    "arguement": "argument",
    "athiest": "atheist",
    "begining": "beginning",
    "beleive": "believe",
    "benifit": "benefit",
    "calender": "calendar",
    "catagory": "category",
    "cemetary": "cemetery",
    "collaegue": "colleague",
    "commitee": "committee",
    "concensus": "consensus",
    "concious": "conscious",
    "dael": "deal",
    "definately": "definitely",
    "dependant": "dependent",
    "desparate": "desperate",
    "develope": "develop",
    "dilema": "dilemma",
    "dissapoint": "disappoint",
    "dissapear": "disappear",
    "ecstacy": "ecstasy",
    "embarass": "embarrass",
    "enviroment": "environment",
    "equiped": "equipped",
    "esential": "essential",
    "exellent": "excellent",
    "existance": "existence",
    "experiance": "experience",
    "familar": "familiar",
    "finaly": "finally",
    "forcast": "forecast",
    "foriegn": "foreign",
    "fourty": "forty",
    "freind": "friend",
    "fufill": "fulfill",
    "goverment": "government",
    "grammer": "grammar",
    "gratitude": "gratitude",
    "guarentee": "guarantee",
    "harrass": "harass",
    "hieght": "height",
    "hierarchy": "hierarchy",
    "humerous": "humorous",
    "hypothesise": "hypothesize",
    "immediatly": "immediately",
    "independant": "independent",
    "indiacate": "indicate",
    "inoculate": "inoculate",
    "irregardless": "regardless",
    "jeapardy": "jeopardy",
    "jewellry": "jewelry",
    "judgement": "judgment",
    "knowlege": "knowledge",
    "legitamate": "legitimate",
    "libary": "library",
    "licence": "license",
    "liten": "litEn",
    "maintainance": "maintenance",
    "managable": "manageable",
    "millenium": "millennium",
    "mischievious": "mischievous",
    "misspell": "misspell",
    "neccessary": "necessary",
    "noticable": "noticeable",
    "occassion": "occasion",
    "occurence": "occurrence",
    "oppurtunity": "opportunity",
    "paralel": "parallel",
    "parliment": "parliament",
    "pasttime": "pastime",
    "peice": "piece",
    "percieve": "perceive",
    "perseverence": "perseverance",
    "phenomenon": "phenomenon",
    "politican": "politician",
    "posession": "possession",
    "practise": "practice",
    "priviledge": "privilege",
    "pronounciation": "pronunciation",
    "publicly": "publicly",
    "recieve": "receive",
    "recomend": "recommend",
    "refered": "referred",
    "refering": "referring",
    "relevent": "relevant",
    "religeous": "religious",
    "remeber": "remember",

    "resistence": "resistance",
    "responsability": "responsibility",
    "restaraunt": "restaurant",
    "rhytm": "rhythm",
    "sargeant": "sergeant",
    "seige": "siege",
    "seperate": "separate",
    "sieze": "seize",
    "similer": "similar",
    "skilful": "skillful",
    "sophmore": "sophomore",
    "speach": "speech",
    "sponser": "sponsor",
    "stragedy": "strategy",
    "strenght": "strength",
    "stubborness": "stubbornness",
    "substract": "subtract",
    "succesful": "successful",
    "supercede": "supersede",
    "supposably": "supposedly",
    "surley": "surely",
    "suround": "surround",
    "tommorow": "tomorrow",
    "tounge": "tongue",
    "truely": "truly",
    "unfortunatly": "unfortunately",
    "untill": "until",
    "vacume": "vacuum",
    "vegitable": "vegetable",
    "villian": "villain",
    "wierd": "weird",
    "writen": "written",
    "acheive": "achieve",
    "agressive": "aggressive",
    "apparantly": "apparently",
    "articule": "article",
    "assasin": "assassin",
}

# Punctuation patterns (pattern, description)
PUNCTUATION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\s,"), "Space before comma"),
    (re.compile(r",\S"), "Missing space after comma"),
    (re.compile(r"\s+\."), "Space before period"),
    (re.compile(r"\.{2}(?!\.)"), "Two periods instead of ellipsis"),
    (re.compile(r"\s+[!?;:]\s*[a-z]"), "Space before exclamation/question/semicolon"),
    (re.compile(r"\([^)]*\("), "Mismatched parentheses"),
    (re.compile(r"\[[^\]]*\["), "Mismatched brackets"),
    (re.compile(r"\"[^\"]*\"[^\"]*\""), "Unbalanced quotes"),
    (re.compile(r"';|;'"), "Reversed semicolon and quote"),
    (re.compile(r"\s{2,}"), "Multiple consecutive spaces"),
]

# Long word (> 9 characters) pattern for readability
LONG_WORD_PATTERN = re.compile(r"\b\w{10,}\b")

# Overused academic phrases
OVERUSED_PHRASES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bin\s+recent\s+years\b", re.I), "Be specific: 'Since 2020' instead of 'In recent years'"),
    (re.compile(r"\ba\s+lot\s+of\b", re.I), "Use 'many', 'several', or 'numerous'"),
    (re.compile(r"\bdue\s+to\s+the\s+fact\b", re.I), "Use 'because' or 'since'"),
    (re.compile(r"\bin\s+other\s+words\b", re.I), "Avoid; just say it directly"),
    (re.compile(r"\bit\s+is\s+important\s+to\s+note\b", re.I), "Delete or rephrase for directness"),
    (re.compile(r"\blast\s+but\s+not\s+least\b", re.I), "Use a more natural transition"),
    (re.compile(r"\bthe\s+fact\s+that\b", re.I), "Simplify: remove 'the fact that'"),
    (re.compile(r"\bit\s+should\s+be\s+noted\b", re.I), "Use active voice: 'Note that...'"),
    (re.compile(r"\bin\s+a\s+nutshell\b", re.I), "Use 'In summary' or 'Briefly'"),
    (re.compile(r"\ball\s+things\s+considered\b", re.I), "Use 'Overall' or 'All factors considered'"),
    (re.compile(r"\bat\s+the\s+end\s+of\s+the\s+day\b", re.I), "Use 'Ultimately' or 'In the end'"),
    (re.compile(r"\bnich\s+of\s+research\b|\bresearch\s+gaps?\b", re.I), "Be specific about what research gap"),
]


# ── Grammar Check ───────────────────────────────────────────────────────────────

@rule(
    id="writing.grammar",
    category="writing",
    name="Grammar check",
    description="Detects common grammar errors in academic/business writing.",
    severity=Severity.MEDIUM,
    priority=28,
    source="syntax-rule",
)
def grammar_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    max_issues = config.get("max_grammar_issues", 10)

    for line_no, line in enumerate(document.lines, 1):
        if len(issues) >= max_issues:
            break

        for pattern, message in COMMON_GRAMMAR_ERRORS:
            m = pattern.search(line)
            if m:
                issues.append(
                    Issue(
                        id=f"writing.grammar-{line_no}",
                        category="writing",
                        rule_id="writing.grammar",
                        severity=Severity.MEDIUM,
                        message=f"{message}: '{m.group()[:60]}'",
                        recommendation=f"Check grammar at line {line_no}: {message}.",
                        evidence=Evidence(
                            line[:200], line_no, line_no, f"line {line_no}",
                        ),
                        confidence=80,
                        source="syntax-rule",
                        autofix_allowed=profile.permissions.get("writing", 0) >= 3,
                    )
                )
                break  # One grammar issue per line

    return issues


# ── Spelling Check ─────────────────────────────────────────────────────────────

@rule(
    id="writing.spelling",
    category="writing",
    name="Spelling check",
    description="Detects common spelling errors and typos.",
    severity=Severity.LOW,
    priority=27,
    source="syntax-rule",
)
def spelling_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    max_issues = config.get("max_spelling_issues", 15)
    word_pattern = re.compile(r"\b\w+\b")

    for line_no, line in enumerate(document.lines, 1):
        if len(issues) >= max_issues:
            break

        for word_match in word_pattern.finditer(line):
            word = word_match.group(0).lower()
            if word in COMMON_TYPOS:
                correction = COMMON_TYPOS[word]
                issues.append(
                    Issue(
                        id=f"writing.spelling-{line_no}-{word}",
                        category="writing",
                        rule_id="writing.spelling",
                        severity=Severity.LOW,
                        message=f"Spelling error: '{word}' should be '{correction}'.",
                        recommendation=f"Replace '{word}' with '{correction}'.",
                        evidence=Evidence(
                            line[:200], line_no, line_no, f"line {line_no}",
                        ),
                        confidence=95,
                        source="syntax-rule",
                        autofix_allowed=True,
                    )
                )
                if len(issues) >= max_issues:
                    break

    return issues


# ── Punctuation Check ──────────────────────────────────────────────────────────

@rule(
    id="writing.punctuation",
    category="writing",
    name="Punctuation check",
    description="Detects common punctuation errors.",
    severity=Severity.LOW,
    priority=26,
    source="syntax-rule",
)
def punctuation_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    max_issues = config.get("max_punctuation_issues", 10)

    for line_no, line in enumerate(document.lines, 1):
        if len(issues) >= max_issues:
            break

        for pattern, message in PUNCTUATION_PATTERNS:
            m = pattern.search(line)
            if m:
                issues.append(
                    Issue(
                        id=f"writing.punctuation-{line_no}",
                        category="writing",
                        rule_id="writing.punctuation",
                        severity=Severity.LOW,
                        message=message + f" (line {line_no})",
                        recommendation=f"Fix punctuation at line {line_no}: {message}.",
                        evidence=Evidence(
                            line[:200], line_no, line_no, f"line {line_no}",
                        ),
                        confidence=90,
                        source="syntax-rule",
                        autofix_allowed=True,
                    )
                )
                break  # One punctuation issue per line

    return issues


# ── Readability Check ──────────────────────────────────────────────────────────

@rule(
    id="writing.readability",
    category="writing",
    name="Readability analysis",
    description="Estimates document readability based on sentence length and word complexity.",
    severity=Severity.LOW,
    priority=23,
    source="semantic-rule",
)
def readability_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    max_long_words_pct = config.get("max_long_words_pct", 25)
    max_avg_sentence_words = config.get("max_avg_sentence_words", 25)

    # Count words and sentences
    all_words = re.findall(r"\b\w+\b", document.text)
    sentences = re.split(r"[.!?]+\s+", document.text)

    if not all_words or len(sentences) < 3:
        return issues

    total_words = len(all_words)
    total_sentences = len([s for s in sentences if len(s.strip().split()) >= 2])

    if total_sentences == 0:
        return issues

    long_words = LONG_WORD_PATTERN.findall(document.text)
    long_word_pct = (len(long_words) / total_words) * 100
    avg_words_per_sentence = total_words / total_sentences

    if long_word_pct > max_long_words_pct:
        issues.append(
            Issue(
                id="writing.readability-complex",
                category="writing",
                rule_id="writing.readability",
                severity=Severity.LOW,
                message=f"Document contains {len(long_words)} long words ({long_word_pct:.0f}% of total).",
                recommendation="Consider using shorter, more common words to improve readability.",
                evidence=Evidence(
                    f"{long_word_pct:.0f}% long words (max: {max_long_words_pct}%)",
                    1, 1, "document",
                ),
                confidence=80,
                source="semantic-rule",
            )
        )

    if avg_words_per_sentence > max_avg_sentence_words:
        issues.append(
            Issue(
                id="writing.readability-long-sentences",
                category="writing",
                rule_id="writing.readability",
                severity=Severity.LOW,
                message=f"Average sentence length is {avg_words_per_sentence:.0f} words (recommended: <= {max_avg_sentence_words}).",
                recommendation="Break down long sentences to improve readability.",
                evidence=Evidence(
                    f"Avg {avg_words_per_sentence:.0f} words/sentence (max: {max_avg_sentence_words})",
                    1, 1, "document",
                ),
                confidence=85,
                source="semantic-rule",
            )
        )

    return issues


# ── Overused Phrases ───────────────────────────────────────────────────────────

@rule(
    id="writing.overused-phrases",
    category="writing",
    name="Overused academic phrases",
    description="Detects clichés and overused phrases in academic writing.",
    severity=Severity.LOW,
    priority=14,
    source="semantic-rule",
)
def overused_phrases_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    max_per_phrase = config.get("max_per_phrase", 2)

    for line_no, line in enumerate(document.lines, 1):
        for pattern, suggestion in OVERUSED_PHRASES:
            if pattern.search(line):
                issues.append(
                    Issue(
                        id=f"writing.overused-{line_no}",
                        category="writing",
                        rule_id="writing.overused-phrases",
                        severity=Severity.LOW,
                        message=f"Overused phrase detected on line {line_no}.",
                        recommendation=suggestion,
                        evidence=Evidence(
                            line[:200], line_no, line_no, f"line {line_no}",
                        ),
                        confidence=85,
                        source="semantic-rule",
                    )
                )
                if len(issues) >= max_per_phrase:
                    return issues

    return issues


# ── Terminology Consistency ────────────────────────────────────────────────────

@rule(
    id="writing.terminology",
    category="writing",
    name="Terminology consistency",
    description="Detects inconsistent use of terminology across the document.",
    severity=Severity.MEDIUM,
    priority=20,
    source="cross-rule",
)
def terminology_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []

    # Common term variants to check for consistency
    term_variants = [
        ("e-mail", "email"),
        ("web site", "website"),
        ("data-base", "database"),
        ("user-friendly", "user friendly"),
        ("state-of-the-art", "state of the art"),
        ("open-source", "open source"),
        ("high-level", "high level"),
        ("real-time", "real time"),
        ("machine-learning", "machine learning"),
        ("deep-learning", "deep learning"),
        ("end-to-end", "end to end"),
        ("well-known", "well known"),
        ("multi-lingual", "multilingual"),
        ("co-operate", "cooperate"),
        ("co-ordinate", "coordinate"),
    ]

    for variant_a, variant_b in term_variants:
        a_count = len(re.findall(re.escape(variant_a), document.text, re.I))
        b_count = len(re.findall(re.escape(variant_b), document.text, re.I))

        if a_count > 0 and b_count > 0:
            total = a_count + b_count
            dominant = variant_a if a_count >= b_count else variant_b
            other = variant_b if a_count >= b_count else variant_a
            issues.append(
                Issue(
                    id=f"writing.terminology-{variant_a.replace(' ', '-')[:20]}",
                    category="writing",
                    rule_id="writing.terminology",
                    severity=Severity.LOW,
                    message=f"Inconsistent terminology: '{variant_a}' ({a_count}x) and '{variant_b}' ({b_count}x).",
                    recommendation=f"Use '{dominant}' consistently instead of '{other}'.",
                    evidence=Evidence(
                        f"'{variant_a}': {a_count}, '{variant_b}': {b_count}",
                        1, 1, "document",
                    ),
                    confidence=90,
                    source="cross-rule",
                )
            )

    return issues


# ── Passive Voice ─────────────────────────────────────────────────────────────

@rule(
    id="writing.passive-voice",
    category="writing",
    name="Passive voice detection",
    description="Detects passive voice constructions that may reduce clarity.",
    severity=Severity.LOW,
    priority=25,
    source="semantic-rule",
)
def passive_voice_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    max_per_doc = config.get("max_passive", 5)
    passive_count = 0

    for line_no, line in enumerate(document.lines, 1):
        matches = PASSIVE_PATTERN.findall(line)
        for match in matches:
            if passive_count >= max_per_doc:
                break
            passive_count += 1
            # Extract the actual verb phrase
            match_start = max(0, line.lower().find(match) - 20)
            context = line[match_start:match_start + 100]

            issues.append(
                Issue(
                    id=f"writing.passive-{line_no}",
                    category="writing",
                    rule_id="writing.passive-voice",
                    severity=Severity.LOW,
                    message="Passive voice detected. Consider using active voice.",
                    recommendation=f"Consider rewriting: '{context.strip()}...' in active voice.",
                    evidence=Evidence(
                        context[:200], line_no, line_no, f"line {line_no}",
                    ),
                    confidence=85,
                    source="semantic-rule",
                    autofix_allowed=profile.permissions.get("writing", 0) >= 3,
                )
            )

    return issues


# ── Hedging & Weak Language ────────────────────────────────────────────────────

@rule(
    id="writing.hedging",
    category="writing",
    name="Hedging language detection",
    description="Detects excessive hedging that weakens claims.",
    severity=Severity.LOW,
    priority=20,
    source="semantic-rule",
)
def hedging_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    max_hedging = config.get("max_hedging", 3)
    hedging_count = 0

    for line_no, line in enumerate(document.lines, 1):
        matches = HEDGING_PATTERN.findall(line)
        for match in matches:
            if hedging_count >= max_hedging:
                break
            hedging_count += 1
            issues.append(
                Issue(
                    id=f"writing.hedging-{line_no}",
                    category="writing",
                    rule_id="writing.hedging",
                    severity=Severity.LOW,
                    message=f"Cautionary word '{match}' weakens the statement.",
                    recommendation="Use more confident language or provide evidence for the claim.",
                    evidence=Evidence(
                        line[:200], line_no, line_no, f"line {line_no}",
                    ),
                    confidence=75,
                    source="semantic-rule",
                    autofix_allowed=profile.permissions.get("writing", 0) >= 4,
                )
            )

    return issues


@rule(
    id="writing.weak-wording",
    category="writing",
    name="Weak wording detection",
    description="Detects weak or vague word choices.",
    severity=Severity.LOW,
    priority=18,
    source="semantic-rule",
)
def weak_wording_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    max_weak = config.get("max_weak", 5)

    for line_no, line in enumerate(document.lines, 1):
        matches = WEAK_PATTERN.findall(line)
        for match in matches[:3]:  # Max 3 per line
            if len(issues) >= max_weak:
                break
            issues.append(
                Issue(
                    id=f"writing.weak-{line_no}",
                    category="writing",
                    rule_id="writing.weak-wording",
                    severity=Severity.LOW,
                    message=f"Weak word: '{match}'. Use more precise language.",
                    recommendation=f"Replace '{match}' with a more specific term.",
                    evidence=Evidence(
                        line[:200], line_no, line_no, f"line {line_no}",
                    ),
                    confidence=70,
                    source="semantic-rule",
                    autofix_allowed=profile.permissions.get("writing", 0) >= 3,
                )
            )

    return issues


# ── Verbosity ──────────────────────────────────────────────────────────────────

@rule(
    id="writing.verbosity",
    category="writing",
    name="Verbose phrases detection",
    description="Detects unnecessarily verbose phrases.",
    severity=Severity.LOW,
    priority=15,
    source="syntax-rule",
)
def verbosity_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []

    for line_no, line in enumerate(document.lines, 1):
        for pattern, suggestion in VERBOSE_PATTERNS:
            if pattern.search(line):
                issues.append(
                    Issue(
                        id=f"writing.verbose-{line_no}",
                        category="writing",
                        rule_id="writing.verbosity",
                        severity=Severity.LOW,
                        message=f"Verbose phrase detected.",
                        recommendation=suggestion,
                        evidence=Evidence(
                            line[:200], line_no, line_no, f"line {line_no}",
                        ),
                        confidence=90,
                        source="syntax-rule",
                        autofix_allowed=profile.permissions.get("writing", 0) >= 3,
                    )
                )
                break  # One issue per line for verbosity

    return issues


# ── Contractions ──────────────────────────────────────────────────────────────

@rule(
    id="writing.contractions",
    category="writing",
    name="Contraction detection",
    description="Detects contractions inappropriate for formal/academic writing.",
    severity=Severity.LOW,
    priority=12,
    source="syntax-rule",
)
def contraction_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    # Check profile-based: academic and SOP should avoid contractions
    if profile.id not in ("academic", "sop"):
        return issues

    for line_no, line in enumerate(document.lines, 1):
        matches = CONTRACTION_PATTERN.findall(line)
        for match in matches:
            issues.append(
                Issue(
                    id=f"writing.contraction-{line_no}",
                    category="writing",
                    rule_id="writing.contractions",
                    severity=Severity.LOW,
                    message=f"Contraction '{match}' used. Avoid contractions in {profile.name} writing.",
                    recommendation=f"Replace '{match}' with its full form.",
                    evidence=Evidence(
                        line[:200], line_no, line_no, f"line {line_no}",
                    ),
                    confidence=95,
                    source="syntax-rule",
                    autofix_allowed=profile.permissions.get("writing", 0) >= 4,
                )
            )

    return issues


# ── Readability ────────────────────────────────────────────────────────────────

@rule(
    id="writing.sentence-length",
    category="writing",
    name="Sentence length check",
    description="Flags overly long sentences that hurt readability.",
    severity=Severity.LOW,
    priority=22,
    source="semantic-rule",
)
def writing_sentence_length(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    max_words = config.get("max_words", 40)

    for line_no, line in enumerate(document.lines, 1):
        # Simple check: split by sentence-ending punctuation
        sentences = re.split(r"[.!?]+", line)
        for sent in sentences:
            words = re.findall(r"\b\w+\b", sent)
            if len(words) > max_words:
                issues.append(
                    Issue(
                        id=f"writing.long-sentence-{line_no}",
                        category="writing",
                        rule_id="writing.sentence-length",
                        severity=Severity.LOW,
                        message=f"Sentence has {len(words)} words (recommended max: {max_words}).",
                        recommendation="Split into shorter sentences for better readability.",
                        evidence=Evidence(
                            sent.strip()[:200], line_no, line_no, f"line {line_no}",
                        ),
                        confidence=88,
                        source="semantic-rule",
                        autofix_allowed=profile.permissions.get("writing", 0) >= 3,
                    )
                )

    return issues


# ── Repetition ─────────────────────────────────────────────────────────────────

@rule(
    id="writing.repetition",
    category="writing",
    name="Word repetition detection",
    description="Detects repeated use of transition words and common terms.",
    severity=Severity.LOW,
    priority=10,
    source="semantic-rule",
)
def repetition_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    max_repeats = config.get("max_repeats", 3)

    # Count transition words
    transition_counts: dict[str, int] = {}
    for line_no, line in enumerate(document.lines, 1):
        for match in REPETITION_WORDS_PATTERN.finditer(line):
            word = match.group(0).lower()
            transition_counts[word] = transition_counts.get(word, 0) + 1

    for word, count in transition_counts.items():
        if count > max_repeats:
            issues.append(
                Issue(
                    id=f"writing.repetition-{word}",
                    category="writing",
                    rule_id="writing.repetition",
                    severity=Severity.LOW,
                    message=f"Transition word '{word}' used {count} times.",
                    recommendation=f"Vary transitions: use synonyms like 'in contrast', 'as a result', 'in addition', etc.",
                    evidence=Evidence(
                        f"'{word}' appears {count} times",
                        1, 1, "document",
                    ),
                    confidence=85,
                    source="semantic-rule",
                )
            )

    return issues


# ── Tone Consistency ───────────────────────────────────────────────────────────

@rule(
    id="writing.tone-consistency",
    category="writing",
    name="Tone consistency check",
    description="Checks for tone inconsistencies (e.g., informal in academic, imperative in business).",
    severity=Severity.MEDIUM,
    priority=15,
    source="semantic-rule",
)
def tone_consistency(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []

    if profile.id == "academic":
        # Academic: avoid informal language
        informal_words = {"gonna", "wanna", "gotta", "kinda", "sorta", "lotsa", "ain't", "yeah", "nah"}
        first_person_count = 0
        for line_no, line in enumerate(document.lines, 1):
            words = set(re.findall(r"\b\w+\b", line.lower()))
            informal = words & informal_words
            for word in informal:
                issues.append(
                    Issue(
                        id=f"writing.informal-{line_no}",
                        category="writing",
                        rule_id="writing.tone-consistency",
                        severity=Severity.MEDIUM,
                        message=f"Informal language '{word}' found. Use formal academic tone.",
                        recommendation=f"Replace '{word}' with a formal equivalent.",
                        evidence=Evidence(
                            line[:200], line_no, line_no, f"line {line_no}",
                        ),
                        confidence=95,
                        source="syntax-rule",
                        autofix_allowed=profile.permissions.get("writing", 0) >= 3,
                    )
                )

    elif profile.id == "business":
        # Business: should be persuasive and action-oriented
        passive_pass = PASSIVE_PATTERN.findall(document.text)
        if len(passive_pass) > 10:
            issues.append(
                Issue(
                    id="writing.business-passive",
                    category="writing",
                    rule_id="writing.tone-consistency",
                    severity=Severity.MEDIUM,
                    message="Excessive passive voice for a business proposal.",
                    recommendation="Use active, persuasive language to engage the reader.",
                    evidence=Evidence(
                        f"{len(passive_pass)} passive constructions found",
                        1, 1, "document",
                    ),
                    confidence=75,
                    source="semantic-rule",
                )
            )

    elif profile.id == "sop":
        # SOP: should use imperative, clear language
        imperative_lines = 0
        for line in document.lines[:20]:
            # Check if starts with imperative verb
            if line.strip() and not line[0].isspace():
                words = line.split()
                if words and words[0][0].isupper():
                    imperative_lines += 1

        if imperative_lines < 3:
            issues.append(
                Issue(
                    id="writing.sop-imperative",
                    category="writing",
                    rule_id="writing.tone-consistency",
                    severity=Severity.MEDIUM,
                    message="SOP should use imperative mood for procedures.",
                    recommendation="Use clear, direct commands (e.g., 'Open the valve' instead of 'The valve should be opened').",
                    evidence=Evidence(
                        "Few imperative sentences detected",
                        1, 1, "document",
                    ),
                    confidence=70,
                    source="semantic-rule",
                )
            )

    return issues
