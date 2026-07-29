from __future__ import annotations

import os
from typing import Any


PLATFORM_VERSION = "0.2.0"
API_VERSION = "1"
RULE_VERSION = "1"
PROMPT_VERSION = "2.0.0"


def build_version_info() -> dict[str, Any]:
    return {
        "platform": PLATFORM_VERSION,
        "api": API_VERSION,
        "rules": RULE_VERSION,
        "prompts": PROMPT_VERSION,
        "commit": os.getenv("REVIEWMIND_COMMIT_SHA", "development"),
        "environment": os.getenv("REVIEWMIND_ENVIRONMENT", "development"),
    }
