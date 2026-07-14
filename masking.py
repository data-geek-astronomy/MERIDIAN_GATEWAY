"""
Masking / unmasking layer sitting between the employee and any external LLM.

mask():   original prompt  -> tokenized prompt (PII/code replaced with
          opaque tokens) + entries written to the token vault.
unmask(): external LLM's response (which may echo back some of those
          tokens) -> rehydrated response, tokens swapped back to real values
          for the authorized internal user only.
"""
from dataclasses import dataclass, field

from detectors.patterns import detect, contains_proprietary_code, Entity
from vault import token_vault


@dataclass
class MaskResult:
    masked_text: str
    entities_found: list[Entity]
    token_counts: dict = field(default_factory=dict)
    code_detected: bool = False


def mask(text: str, session_id: str) -> MaskResult:
    entities = detect(text)
    token_counts: dict[str, int] = {}
    masked = text
    offset = 0

    for e in entities:
        token_counts[e.label] = token_counts.get(e.label, 0) + 1
        token = f"<<{e.label}_{token_counts[e.label]}>>"
        token_vault.store(session_id, token, e.text, e.label)

        start = e.start + offset
        end = e.end + offset
        masked = masked[:start] + token + masked[end:]
        offset += len(token) - (e.end - e.start)

    code_detected = contains_proprietary_code(text)
    if code_detected:
        token_counts["PROPRIETARY_CODE_BLOCK"] = token_counts.get("PROPRIETARY_CODE_BLOCK", 0) + 1
        code_token = f"<<PROPRIETARY_CODE_BLOCK_{token_counts['PROPRIETARY_CODE_BLOCK']}>>"
        token_vault.store(session_id, code_token, text, "PROPRIETARY_CODE_BLOCK")
        masked = f"{code_token}\n[Full snippet withheld from external model -- see internal audit log for original]"

    return MaskResult(
        masked_text=masked,
        entities_found=entities,
        token_counts=token_counts,
        code_detected=code_detected,
    )


def unmask(text: str, session_id: str) -> str:
    result = text
    for token, original_value, _label in token_vault.all_entries(session_id):
        if token in result:
            result = result.replace(token, original_value)
    return result
