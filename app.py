import json
import os
import uuid

import streamlit as st

from gateway import process_request
from vault import token_vault

st.set_page_config(page_title="Meridian Gateway | Enterprise LLM DLP", page_icon="🛡️", layout="wide")

# ---------------------------------------------------------------------------
# Theme: navy / steel blue, dense, institutional -- Wall Street terminal feel
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    :root {
        --mer-navy: #0A1F44;
        --mer-blue: #1B4CD1;
        --mer-steel: #142850;
        --mer-grey: #8FA3C7;
    }
    .stApp { background-color: var(--mer-navy); color: #EAF0FB; }
    section[data-testid="stSidebar"] { background-color: var(--mer-steel); }
    h1, h2, h3 { font-family: -apple-system, 'Helvetica Neue', sans-serif; letter-spacing: -0.01em; }
    .mer-hero { font-size: 2.0rem; font-weight: 700; margin-bottom: 0; }
    .mer-sub { color: var(--mer-grey); font-size: 0.95rem; margin-top: 0.2rem; }
    .mer-card {
        background: var(--mer-steel); border: 1px solid #24345E; border-radius: 12px;
        padding: 14px 16px; margin-bottom: 10px;
    }
    .mer-token { color: #FFC857; font-family: monospace; }
    div[data-testid="stMetricValue"] { color: #EAF0FB; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    st.markdown("### 🛡️ Meridian Gateway")
    st.caption("Self-hosted LLM proxy — PII & IP masking, DLP for external AI calls")

    llm_mode = st.radio(
        "External model",
        options=["mock", "real"],
        format_func=lambda m: "Mock external LLM (offline)" if m == "mock" else "Real Claude call (needs ANTHROPIC_API_KEY)",
    )
    if llm_mode == "real" and not os.environ.get("ANTHROPIC_API_KEY"):
        st.warning("No ANTHROPIC_API_KEY set — will fall back to mock.")

    st.divider()
    with open(os.path.join(os.path.dirname(__file__), "data", "sample_prompts.json")) as f:
        samples = json.load(f)["examples"]
    labels = {s["label"]: s["prompt"] for s in samples}
    chosen = st.selectbox("Load a synthetic sample prompt", options=["(blank)"] + list(labels.keys()))

    st.divider()
    if st.button("Reset session"):
        token_vault.clear_session(st.session_state.session_id)
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.history = []
        st.rerun()

    st.divider()
    st.markdown("#### 🔐 Token vault (this session)")
    entries = token_vault.all_entries(st.session_state.session_id)
    if not entries:
        st.caption("Empty — nothing masked yet.")
    else:
        for token, original, label in entries[-10:]:
            st.markdown(
                f'<div class="mer-card"><span class="mer-token">{token}</span><br>'
                f'<span style="color:var(--mer-grey); font-size:0.8rem;">{label} → never leaves this vault</span></div>',
                unsafe_allow_html=True,
            )

st.markdown('<div class="mer-hero">Meridian Enterprise AI Gateway</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="mer-sub">Every prompt is scrubbed of PII and proprietary code before it reaches an '
    'external model — and rehydrated only for you, on the way back.</div>',
    unsafe_allow_html=True,
)
st.write("")

default_text = labels.get(chosen, "")
prompt = st.text_area("Employee prompt (as if pasted into a public chatbot)", value=default_text, height=140)

col1, col2 = st.columns([1, 5])
with col1:
    run = st.button("Send through gateway", type="primary")

if run and prompt.strip():
    result = process_request(prompt, st.session_state.session_id, llm_mode=llm_mode)
    st.session_state.history.insert(0, result)

if st.session_state.history:
    latest = st.session_state.history[0]
    n_entities = len(latest.mask_result.entities_found) + (1 if latest.mask_result.code_detected else 0)

    m1, m2, m3 = st.columns(3)
    m1.metric("Sensitive items masked", n_entities)
    m2.metric("Entity types caught", len(latest.mask_result.token_counts))
    m3.metric("Reached external LLM", "0 raw PII bytes" if n_entities else "n/a (nothing sensitive)")

    st.markdown("#### 1. What the external LLM actually saw")
    st.code(latest.masked_prompt or "(empty)")

    st.markdown("#### 2. External LLM's raw (still-masked) reply")
    st.code(latest.external_response_masked)

    st.markdown("#### 3. Final response shown to you (rehydrated)")
    st.success(latest.final_response)

    if latest.mask_result.token_counts:
        with st.expander("Detection breakdown"):
            for label, count in latest.mask_result.token_counts.items():
                st.write(f"- **{label}**: {count} instance(s) masked")

st.divider()
st.markdown("#### Session history")
for r in st.session_state.history[1:6]:
    with st.expander(r.original_prompt[:80] + ("..." if len(r.original_prompt) > 80 else "")):
        st.caption("Masked prompt sent externally:")
        st.code(r.masked_prompt)
        st.caption("Final rehydrated response:")
        st.write(r.final_response)
