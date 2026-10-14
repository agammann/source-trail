"""Optional live Source Trail demo using a small local model."""

import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

# Community Cloud runs an entrypoint inside demo/; import the unchanged repository core.
repository = str(Path(__file__).resolve().parents[1])
if repository not in sys.path:
    sys.path.insert(0, repository)

import streamlit as st

from demo.bootstrap import DemoBusy, DemoRuntime, MODEL, PAGE_BUDGET, RuntimeUnavailable


st.set_page_config(page_title="Source Trail", page_icon="🔎", layout="wide")


@st.cache_resource(show_spinner=False)
def runtime():
    return DemoRuntime()


def source_link(url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password:
            st.link_button("Open source", url)
        st.text(url)
    except (TypeError, ValueError):
        st.text("Source URL unavailable")


st.title("Source Trail")
st.subheader("Answers you can trace.")
st.caption("A live prototype by agammann")
st.info("This live extractive demo uses Qwen3 0.6B to select one relevant source passage from up to four candidates. "
        "It returns that passage verbatim, using a separate passage-selection prompt. "
        "The full AMD app uses Qwen3-4B-Instruct-2507 to produce short answers and was validated on an MI300X. "
        "This demo makes fresh requests; it does not replay AMD responses.")

left, right = st.columns([1, 1.2], gap="large")
with left:
    with st.form("query"):
        question = st.text_area("Question", max_chars=2000, height=110,
                                placeholder="What happens to other tasks when one task in a TaskGroup fails?")
        urls_text = st.text_area("Starting URLs", max_chars=6000, height=100,
                                 placeholder="https://docs.python.org/3/library/asyncio-task.html")
        version = st.text_input("Target version", max_chars=40, placeholder="Optional")
        st.caption(f"One public URL per line, up to {PAGE_BUDGET} starting pages. "
                   f"Verified retrieval with a {PAGE_BUDGET}-page budget. Static HTML and plain text only.")
        submitted = st.form_submit_button("Run live query", type="primary", width="stretch")
    st.caption("The first model startup may take several minutes. Later queries reuse the local runtime. "
               "The selected passage can be incomplete or irrelevant; inspect its source. "
               "This mode does not synthesize across sources or establish version comparisons.")
    with st.expander("Example inputs"):
        st.text("Question: What happens to other tasks when one task in a TaskGroup fails?")
        st.code("https://docs.python.org/3/library/asyncio-task.html", language=None)
    st.link_button("Source and AMD validation evidence", "https://github.com/agammann/source-trail")

if submitted:
    st.session_state.pop("result", None)
    urls = [url.strip() for url in urls_text.splitlines() if url.strip()]
    try:
        with st.spinner("Retrieving evidence and preparing the local model if needed…"):
            st.session_state["result"] = runtime().run_query(question.strip(), urls, version.strip() or None)
    except DemoBusy as error:
        st.warning(str(error))
    except ValueError as error:
        st.error(str(error))
    except (OSError, RuntimeUnavailable):
        st.error("The local model runtime is unavailable. Try again after startup finishes or the app restarts.")
    except Exception:
        st.error("The query could not be completed. No answer is being supplied.")

with right:
    st.header("Evidence")
    result = st.session_state.get("result")
    if result is None:
        st.text("Run a query to inspect the answer, exact quotes, source versions, and navigation path.")
    else:
        status = result.get("status", "failed")
        st.text("Status: " + status)
        if status == "answered":
            st.caption("Model-selected source passage, copied verbatim")
        explanations = {"abstained": "The available evidence did not establish an answer.",
                        "conflict": "The retrieved sources conflict. Inspect their quotes.",
                        "failed": "The query could not be completed."}
        scope_limit = result.get("demo_selection", {}).get("scope_limit")
        st.text(result.get("answer") or scope_limit or explanations.get(status, "No answer returned."))
        if result.get("error"):
            st.text(result["error"])
        metrics = result.get("metrics", {})
        st.caption("Recorded values from this fresh query")
        st.json({key: metrics.get(key) for key in ("pages", "model_calls", "input_tokens", "output_tokens", "duration_ms")})
        st.subheader("Supporting quotes")
        for citation in result.get("citations", []):
            source_link(citation.get("url"))
            st.text(citation.get("quote", ""))
            st.caption(f"Block {citation.get('block_id', '')} · Version {citation.get('source_version') or 'not identified'}")
        if not result.get("citations"):
            st.text("No supporting quotes returned.")
        with st.expander("Source versions"):
            for source in result.get("sources", []):
                st.text(source.get("title", ""))
                source_link(source.get("url"))
                st.text("Version: " + (source.get("version") or "not identified"))
        with st.expander("Navigation path"):
            st.json(result.get("trace", []))
        st.download_button("Download JSON", json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           file_name="source-trail-result.json", mime="application/json")
