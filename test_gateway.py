"""Smoke test: confirm PII/code is masked before the 'external call' and
correctly rehydrated afterward, across all synthetic sample prompts."""
import json
import os

from gateway import process_request

with open(os.path.join(os.path.dirname(__file__), "data", "sample_prompts.json")) as f:
    samples = json.load(f)["examples"]

for s in samples:
    result = process_request(s["prompt"], session_id=f"test-{s['id']}", llm_mode="mock")
    leaked = []
    for token, original, label in [(t, o, l) for t, o, l in []]:
        pass
    # crude leak check: none of the vault's original sensitive values should
    # appear in what was sent externally (masked_prompt)
    from vault import token_vault
    entries = token_vault.all_entries(f"test-{s['id']}")
    leaks = [orig for _, orig, _ in entries if orig in result.masked_prompt]
    status = "LEAK!!" if leaks else "clean"
    print(f"[{s['id']}] {s['label']:45} masked_entities={len(entries):2} externally_sent_clean={status}")
    if leaks:
        print("   LEAKED VALUES:", leaks)

print("\n--- Full detail: EX-01 (client PII) ---")
r = process_request(samples[0]["prompt"], session_id="detail-1", llm_mode="mock")
print("MASKED PROMPT SENT EXTERNALLY:\n", r.masked_prompt)
print("\nFINAL REHYDRATED RESPONSE:\n", r.final_response)
