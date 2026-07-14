"""
Lightweight, dependency-free NER for the DLP gateway demo.

Production note: this stands in for the "asynchronous pipeline using Apache
Kafka and a lightweight NER model (custom spaCy or BERT-based)" from the
architecture brief. Regex + curated patterns keep this demo runnable
anywhere with zero model downloads and zero external services, while
exercising the exact same interface (`detect(text) -> list[Entity]`) a real
spaCy/BERT NER model or a Kafka consumer stage would implement. Swap
`RegexEntityDetector` for a real model without touching the gateway,
masking, or vault logic.
"""

from __future__ import annotations
import re
from dataclasses import dataclass

COMMON_CAP_WORDS = {
    "I", "The", "Can", "Here", "His", "Her", "He", "She", "Draft", "Please",
    "Account", "SSN", "DOB", "Reach", "AirNova", "RiskEngine", "Client",
}


@dataclass
class Entity:
    label: str
    text: str
    start: int
    end: int


_PATTERNS = [
    ("EMAIL", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("PHONE", re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b")),
    ("DOB", re.compile(r"\b(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])/(19|20)\d{2}\b")),
    ("ACCOUNT_NUMBER", re.compile(r"\b\d{4}-\d{4}-\d{4}\b|account\s*#?\s*\d{4}-\d{4}-\d{4}", re.IGNORECASE)),
    ("ROUTING_NUMBER", re.compile(r"routing\s*\d{9}", re.IGNORECASE)),
    ("CARD_LAST4", re.compile(r"card ending\s*\d{4}", re.IGNORECASE)),
    ("IP_ADDRESS", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("SERVICE_ACCOUNT", re.compile(r"\bsvc_[a-z0-9_]+\b", re.IGNORECASE)),
    ("INTERNAL_SYSTEM", re.compile(r"\b[A-Z][a-zA-Z]+(?:Engine|Cluster|Gateway|Prod|DB)-?(?:Prod|Staging|Dev)?\b")),
    ("STREET_ADDRESS", re.compile(r"\b\d{1,5}\s+[A-Z][a-zA-Z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr)\b.*?(?:\d{5})?", re.IGNORECASE)),
    ("DOLLAR_AMOUNT", re.compile(r"\$[\d,]+(?:\.\d{2})?")),
    ("CONSTANT_IDENTIFIER", re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+){2,}\b")),
    ("PERSON_NAME", re.compile(r"\b[A-Z][a-z]+\s[A-Z][a-z]+\b")),
]

CODE_SIGNATURE = re.compile(r"\bdef\s+\w+\(|\bclass\s+\w+|import\s+\w+|\breturn\b.*[:=]")


def detect(text: str) -> list[Entity]:
    entities: list[Entity] = []
    for label, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            value = m.group(0)
            if label == "PERSON_NAME":
                first_word = value.split()[0]
                if first_word in COMMON_CAP_WORDS:
                    continue
            entities.append(Entity(label=label, text=value, start=m.start(), end=m.end()))
    entities.sort(key=lambda e: e.start)
    return _drop_overlaps(entities)


def _drop_overlaps(entities: list[Entity]) -> list[Entity]:
    """If two entities overlap (e.g. ACCOUNT_NUMBER inside a longer STREET_ADDRESS
    match), keep the longer / more specific one and drop the rest."""
    kept: list[Entity] = []
    for e in sorted(entities, key=lambda e: (e.start, -(e.end - e.start))):
        if any(not (e.end <= k.start or e.start >= k.end) for k in kept):
            continue
        kept.append(e)
    kept.sort(key=lambda e: e.start)
    return kept


def contains_proprietary_code(text: str) -> bool:
    return bool(CODE_SIGNATURE.search(text))
