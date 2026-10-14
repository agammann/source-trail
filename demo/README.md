# Source Trail live extractive demo

This optional Streamlit app by **agammann** retrieves fresh public web evidence and uses local Ollama `qwen3:0.6b` to select one relevant passage. It copies the selected passage into the result and citation, then applies Source Trail's existing quote and version validation. It does not replay saved answers.

The free [public demo](https://source-trail.streamlit.app/) completed fresh TaskGroup and license questions on October 13, 2026. See [the hosted validation record](../evidence/demo/cloud-checks.json). Those checks establish the observed startup and inference, not uptime, peak memory usage, or general retrieval quality.

This is a separate **extractive-selector-v1** profile. The full AMD-validated application uses Qwen3-4B-Instruct-2507 and a different prompt to produce short answers. Its benchmark results do not describe this smaller demo.

The demo uses verified retrieval with a three-page budget. It considers at most four ranked passages, bounds the serialized selection prompt to 3,500 UTF-8 bytes, and requests a 4,096-token context with at most 64 generated tokens. Excerpts remain exact prefixes of source text and contain at most 1,200 characters. One shared lock permits one query at a time; results stay in each visitor's Streamlit session. The model and its loopback endpoint cannot be selected through the form.

The selected passage can be irrelevant or incomplete. Exact quote validation proves text occurrence, not that the passage fully answers the question. This profile abstains on recognized version comparisons and does not combine multiple sources or resolve their conflicts. HTML/plain-text reading and the core's public-address restrictions remain in effect. Missing token usage stays unavailable; malformed or incomplete model responses do not become answers.

## Run locally

Use Python 3.12 and run these commands from the repository root. On Windows, start an installed Ollama service on `127.0.0.1:11434` first:

```powershell
py -3.12 -m venv .venv-demo
.\.venv-demo\Scripts\python.exe -m pip install -r demo\requirements.txt
ollama pull qwen3:0.6b
.\.venv-demo\Scripts\python.exe -m streamlit run demo\app.py --server.address 127.0.0.1 --server.port 8501
```

On Linux, use a separate environment:

```bash
python3.12 -m venv .venv-demo
.venv-demo/bin/python -m pip install -r demo/requirements.txt
.venv-demo/bin/python -m streamlit run demo/app.py --server.address 127.0.0.1 --server.port 8501
```

Open [the local demo](http://127.0.0.1:8501), enter one short question and public starting URLs, then select **Run live query**. Inspect the selected passage, quotes, source versions, navigation, and downloadable JSON. Requests do not contain expected answers. Restart Streamlit after changing the runtime/profile code to discard an old cached resource.

## Community Cloud configuration

After these files are present on GitHub, deploy repository `agammann/source-trail`, branch `main`, entrypoint **`demo/app.py`**, with **Python 3.12**. No secrets or paid inference services are required. Streamlit uses the [requirements beside the entrypoint](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies): Streamlit 1.65.0 and zstandard 0.25.0. The demo imports the existing repository core directly.

When inference is first needed, the bootstrap reuses a running local Ollama service or, on Linux x86-64, downloads the official **Ollama 0.40.3** archive into `~/.cache/source-trail-demo`, verifies its pinned SHA-256, retains its binary/library layout, and launches it on loopback. It then pulls `qwen3:0.6b` if absent and checks its registry digest. Installation requires no system service or privileged installer. The managed runtime disables Ollama cloud access and limits loaded models and parallel inference to one. Other operating systems need an existing Ollama service.

The [model download](https://ollama.com/library/qwen3:0.6b) is approximately 523 MB; the [pinned Linux runtime archive](https://github.com/ollama/ollama/releases/tag/v0.40.3) is approximately 1.44 GB. Download size is not peak RAM usage. First startup can take several minutes and can fail if resource, network, or startup-time limits are reached. Native-runtime compatibility, available memory, cold start, and real queries must be checked on the deployed host before claiming a working online demo.

Community Cloud's published [resource limits](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app) are approximate and may change. Apps can sleep, and [local files are not guaranteed to persist](https://docs.streamlit.io/develop/concepts/connections/connecting-to-data), so a restart may require new runtime/model downloads. The app checks service readiness on each inference attempt and preserves errors rather than substituting a saved answer.

## Tests without model dependencies

These tests need only Python and the repository source. They do not import Streamlit, install Ollama, download weights, or make inference requests:

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s demo/tests -v
```

CI runs both suites on Ubuntu and Windows with Python 3.11 and 3.12. The demo tests cover fixed public-source controls, concurrency, quote validation, selection parsing, prompt bounds, usage accounting, and bootstrap checksum/path checks. Fixture tests do not establish public hosting or live-model success.
