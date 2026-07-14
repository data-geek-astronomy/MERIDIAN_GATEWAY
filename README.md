---
title: MERIDIAN GATEWAY
emoji: 🛡️
colorFrom: blue
colorTo: gray
sdk: streamlit
sdk_version: "1.38.0"
python_version: "3.10"
app_file: app.py
pinned: false
---

# Meridian Gateway — Enterprise LLM DLP Proxy

**[View the project landing page](docs/index.html)** (enable GitHub Pages on this repo to host it live — see below) &middot; **[Live interactive demo](https://huggingface.co/spaces/Darkweb007/MERIDIAN_GATEWAY)**

**Portfolio project 2 of 5** — a demo response to the "Shadow AI" problem
Wall Street firms like JPMorgan Chase, Citi, and Goldman Sachs have
restricted or banned public LLM use over: employees pasting proprietary
trading code or client PII into ChatGPT-style tools, with no way to audit
or prevent it. This project is a self-hosted proxy that sits between every
employee and any external LLM, strips sensitive data out before it leaves
the building, and rehydrates the response afterward.

> ⚠️ **All data in this project is synthetic.** `data/sample_prompts.json`
> contains fabricated names, account numbers, SSNs, and a fake trading
> algorithm snippet, invented for this demo. No real client, employee, or
> proprietary data is used anywhere in this repo.

## Why this exists

The risk isn't that employees are malicious — it's that copy-pasting a
client's SSN into a public chatbot for "just a quick summary," or dropping
a proprietary pricing model in to "clean up the code," leaks regulated data
and IP to a third party with no contractual guarantee it won't be logged,
trained on, or breached. Blocking LLM use entirely kills productivity;
trusting employees to self-censor doesn't scale. The fix is a mandatory
gateway: nothing reaches an external model without passing through a
masking layer first.

## Architecture

```
employee prompt
    |
    v
[detect()]  regex/NER over PII, financial identifiers, code signatures
            <- detectors/patterns.py (stand-in for a fine-tuned spaCy/BERT NER model)
    |
    v
[mask()]    replace each hit with an opaque token (<<EMAIL_1>>, <<SSN_1>>, ...)
            write token -> original value into the token vault
            <- masking.py, vault/token_vault.py
    |
    v
[async queue]  <- queue_sim.py (stand-in for the Kafka producer/consumer pipeline)
    |
    v
[external LLM call]   receives ONLY the masked prompt — zero raw PII/IP ever leaves
    |
    v
[unmask()]  tokens in the LLM's response are resolved back to real values
            for the authorized internal user
    |
    v
final response, only ever seen by the employee who submitted it
```

The token vault (`vault/token_vault.py`, SQLite-backed here) never leaves
the internal network boundary in this design — only opaque tokens do.

## Try it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Pick a synthetic sample prompt from the sidebar (client PII, a fake trading
algorithm, an internal system name + service account) and click **Send
through gateway**. The UI shows all three stages: what the external model
actually received (fully masked), its raw masked reply, and the final
rehydrated response — so you can see exactly what would and wouldn't have
leaked without this layer in front of it.

### Real LLM mode

Set `ANTHROPIC_API_KEY` and switch to "Real Claude call" to route the
*masked* prompt to a real model instead of the offline mock. The system
prompt explicitly instructs the model to preserve `<<TOKEN>>` placeholders
verbatim — demonstrating that masking works independent of which model is
on the other side of the gateway.

## Project structure

```
llm-gateway-dlp/
├── app.py                    # Streamlit UI
├── gateway.py                 # orchestrates mask -> queue -> external call -> unmask
├── masking.py                 # mask()/unmask() logic
├── queue_sim.py                # in-process stand-in for the Kafka pipeline
├── detectors/
│   └── patterns.py            # regex/NER PII + proprietary-code detection
├── vault/
│   └── token_vault.py         # SQLite-backed token -> original-value store
├── data/
│   └── sample_prompts.json    # SYNTHETIC example employee prompts
└── requirements.txt
```

## Production upgrade path

| Demo component | Production equivalent |
|---|---|
| Regex/pattern NER | Fine-tuned spaCy or BERT-based NER model, trained on the org's own entity taxonomy |
| `queue_sim.py` in-process queue | Apache Kafka producer/consumer, with dead-letter topics for failed masking |
| SQLite in-memory vault | Encrypted, access-controlled KV store (Vault/KMS-backed), per-session TTL, full audit trail on every read |
| Rule-based code-snippet flag | AST-aware static analysis + secrets scanning (e.g. detect-secrets, TruffleHog) layered on top |

## Project landing page

`docs/index.html` is a standalone, single-file static landing page (no build step) summarizing the project's results, method, and findings. To host it live on GitHub Pages: repo **Settings → Pages → Source: Deploy from a branch → Branch: main, folder: /docs → Save**. It'll be live within a minute or two at `https://data-geek-astronomy.github.io/MERIDIAN_GATEWAY/`.
