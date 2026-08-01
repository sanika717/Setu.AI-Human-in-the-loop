import re

PROMPT_INJECTION_PATTERNS = [
    r"\bignore (previous instructions|this|all previous directives)\b",
    r"\bdisregard (previous instructions|this|all previous directives)\b",
    r"\breset your instructions\b",
    r"\bcontinue with the task\b",
    r"\bopenai key\b",
    r"\bapi key\b",
    r"\bmalicious\b",
]


def detect_prompt_injection(text: str) -> bool:
    normalized = text.lower()
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, normalized):
            return True
    return False
