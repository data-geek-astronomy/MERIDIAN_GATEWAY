"""
The gateway: the single choke point every internal AI request must route
through before it reaches a public/external LLM. Mirrors the "centralized
proxy server/gateway API" from the architecture brief -- Kafka is simulated
here with a simple in-process queue (see `queue_sim.py`) since a real Kafka
cluster isn't needed to demonstrate the masking/unmasking contract.

    employee prompt
        |
        v
    [mask()]  regex/NER PII + proprietary-code detector -> tokens + vault write
        |
        v
    [async queue]  (Kafka stand-in, see queue_sim.py)
        |
        v
    [external LLM call]   ONLY ever sees masked_prompt, never raw PII/code
        |
        v
    [unmask()]  tokens in the LLM's response are resolved back to real values
        |
        v
    response shown to employee (external LLM never saw the sensitive data)
"""
import os
from dataclasses import dataclass, field

from masking import mask, unmask, MaskResult
from queue_sim import enqueue_and_process


@dataclass
class GatewayResult:
    session_id: str
    original_prompt: str
    masked_prompt: str
    external_response_masked: str
    final_response: str
    mask_result: MaskResult


def mock_external_llm(masked_prompt: str) -> str:
    lower = masked_prompt.lower()
    if "summarize" in lower:
        body = masked_prompt.split(":", 1)[-1].strip()
        return f"Summary: {body}"
    if "draft" in lower or "email" in lower:
        return f"Here's a draft:\n\n{masked_prompt}\n\nLet me know if you'd like any edits."
    if "PROPRIETARY_CODE_BLOCK" in masked_prompt or "optimize" in lower or "debug" in lower:
        return (
            f"Here's my take on what you shared:\n\n{masked_prompt}\n\n"
            "Suggestions: vectorize the rolling computations, cache intermediate "
            "results, and consider batching requests to reduce latency."
        )
    return f"Sure, here's my response:\n\n{masked_prompt}"


def real_external_llm(masked_prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    system_prompt = (
        "You are a general-purpose assistant. The user's message may contain "
        "placeholder tokens like <<EMAIL_1>> or <<PERSON_NAME_1>> -- these represent "
        "sensitive data that has been redacted before reaching you. Preserve every "
        "such token EXACTLY as written in your response; never guess, invent, or "
        "omit the value they stand for."
    )
    resp = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=400,
        system=system_prompt,
        messages=[{"role": "user", "content": masked_prompt}],
    )
    return resp.content[0].text


def process_request(prompt: str, session_id: str, llm_mode: str = "mock") -> GatewayResult:
    mask_result = mask(prompt, session_id)

    def call_llm(masked_text: str) -> str:
        if llm_mode == "real" and os.environ.get("ANTHROPIC_API_KEY"):
            try:
                return real_external_llm(masked_text)
            except Exception as e:  # pragma: no cover
                return mock_external_llm(masked_text) + f"\n\n[real-LLM call failed, showed mock output: {e}]"
        return mock_external_llm(masked_text)

    external_response_masked = enqueue_and_process(mask_result.masked_text, call_llm)
    final_response = unmask(external_response_masked, session_id)

    return GatewayResult(
        session_id=session_id,
        original_prompt=prompt,
        masked_prompt=mask_result.masked_text,
        external_response_masked=external_response_masked,
        final_response=final_response,
        mask_result=mask_result,
    )
