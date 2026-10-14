# Source Trail

Source Trail retrieves web evidence for a question and makes the answer, supporting quotes, source versions, and navigation path inspectable. It is a local prototype by **agammann**, [submitted to the AMD AI League under Ammann Labs](https://lablab.ai/ai-hackathons/amd-lablab-ai-academy-challenge/ammann-labs/source-trail).

The project explores a specific question: can a retrieval workflow handle stale pages, conflicting sources, and missing answers more reliably than a simpler workflow under the same page budget? Its synthetic fixtures provide a way to inspect those cases. They do not establish originality, broad web performance, or a competitive score.

## Challenge status

Checked on **October 13, 2026**: the organizer lists Match 4, *Intelligent Web Information Retrieval*, as live for October 13–27. Its public description calls for an agent that navigates websites and retrieves specific information from a natural-language request. The Match 4 detail link still opens the overview, and the visible starter kit is labeled Match 3. A detailed Match 4 interface, evaluator, runtime contract, and inference rules were not available from those links. See the [official challenge page](https://lablab.ai/ai-hackathons/amd-lablab-ai-academy-challenge).

The LabLab project entry was successfully submitted under **Ammann Labs**. Its public page displays October 14, 2026; the [submission receipt](evidence/lablab-submission.json) records verification at 2026-10-14 04:45:39 UTC and the local date of October 13. This published entry precedes the detailed Match 4 brief and does not establish an official evaluator score or runtime compatibility. A specific development run on an AMD Instinct MI300X through the general notebook tutorial service is verified. The default connector uses local Ollama; an operator-selected local vLLM connector supports the tested AMD runtime.

The submitted source snapshot is `babe608e31d5f672baf27550487102ba6a06f550`; AMD model validation used `7e406424b14ce49a77352111c51f5ae7980df4f0`. The existing source ZIP, evidence ZIP, manifest and wheel remain frozen at that submitted snapshot. These later receipt and documentation updates do not change those downloads.

## Run locally

Use Python 3.11 or later and a running [Ollama](https://ollama.com/) instance. The Python coordinator has no third-party runtime dependencies. Run commands from the project root.

On Windows, the helper selects a working interpreter from an explicit `-PythonPath`, the `SOURCETRAIL_PYTHON` environment variable, a project `.venv`, or the standard Python launcher/commands. It rejects candidates that fail the version check, including inactive Microsoft Store aliases.

```powershell
.\run.ps1 -Check
ollama list
```

To choose an interpreter explicitly, replace this example path with your Python executable:

```powershell
.\run.ps1 -PythonPath "C:\Python312\python.exe" -Check
```

A project virtual environment is optional. Create one with a working Python interpreter using `python -m venv .venv`. In the CLI examples below, `python` means that working interpreter; on Windows, you can use `.\.venv\Scripts\python.exe` in its place if it is not on `PATH`.

The default model is `qwen3.5:4b-q4_K_M`. If it is not already installed, pull it before running a query:

```powershell
ollama pull qwen3.5:4b-q4_K_M
```

An endpoint and model can be configured for the local process:

```powershell
$env:SOURCETRAIL_OLLAMA_URL = "http://127.0.0.1:11434"
$env:SOURCETRAIL_MODEL = "qwen3.5:4b-q4_K_M"
```

Start the evidence inspector on Windows:

```powershell
.\run.ps1
```

Use `-Port 8766` to choose another local port. On Linux or macOS, start it directly:

```bash
python3 -m sourcetrail serve --host 127.0.0.1 --port 8765
```

Open [the local inspector](http://127.0.0.1:8765). Enter a question and one URL per line, optionally add a target version, and select **Run query**. The example buttons fill the form with public documentation questions; they do not run a query or supply an answer. After a result arrives, inspect quotes, expand source versions and the navigation path, or download its JSON.

Keep the service bound to loopback. The browser does not select or change the model endpoint.

## Run with local vLLM on an AMD notebook

The general [AMD notebook portal](https://notebooks.amd.com/) provides One-Click Tutorials separately from hackathon registration. The recorded run used its vLLM tutorial environment with one MI300X virtual function, ROCm-enabled PyTorch, and the pinned [Qwen3-4B-Instruct-2507 model](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507). The full runtime versions and weight revision are in [the AMD verification record](evidence/amd/verification.json).

In an environment with ROCm-enabled vLLM already installed, start the model server:

```bash
vllm serve Qwen/Qwen3-4B-Instruct-2507 \
  --revision cdbee75f17c01a7cc42f958dc650907174af0554 \
  --served-model-name Qwen3-4B-Instruct-2507 \
  --host 127.0.0.1 --port 8000 --max-model-len 8192 \
  --gpu-memory-utilization 0.2 --max-num-seqs 1 \
  --enforce-eager --generation-config vllm --dtype bfloat16
```

Run Source Trail in another terminal in the same environment:

```bash
export SOURCETRAIL_PROVIDER=vllm
export SOURCETRAIL_VLLM_URL=http://127.0.0.1:8000/v1
export SOURCETRAIL_MODEL=Qwen3-4B-Instruct-2507
python -m sourcetrail query --question "What happens to other tasks when one task in a TaskGroup fails?" --url "https://docs.python.org/3/library/asyncio-task.html" --mode verified --output results/taskgroup.json
```

The CLI also accepts `--provider vllm --model Qwen3-4B-Instruct-2507`. The endpoint must be loopback HTTP(S), with an optional `/v1` base path. Optional `SOURCETRAIL_VLLM_API_KEY` authentication stays in the operator's environment and is sent only as a header to that local runtime. The vLLM client bypasses proxies and redirects, requests structured JSON, rejects incomplete responses, and preserves unavailable token counts as null. Both connectors share the evidence prompt and final quote/version validation.

The AMD run completed 44 model requests with recorded responses, server token metrics, and overlapping GPU activity samples. Its fresh [Python TaskGroup query](evidence/amd/results/live-python-taskgroup.json) answered with an exact quote retaining the exception qualifier. These records establish that particular development run; official evaluator and container validation remain pending.

## Query from the CLI

```powershell
python -m sourcetrail query --question "What happens to other tasks when one task in a TaskGroup fails?" --url "https://docs.python.org/3/library/asyncio-task.html" --mode verified --max-pages 6 --output results\taskgroup.json
```

Optional controls include `--target-version`, `--model`, and `--allow-local`. The last option is intended for a trusted loopback fixture server. Public queries use the default URL checks. Use `python -m sourcetrail query --help` for the complete interface.

Long text blocks are split into overlapping exact passages before relevance ranking. Table rows retain their HTML heading and column context. Each proposed quote is checked before duplicate source-and-quote pairs are collapsed; results contain at most ten distinct citations.

Two modes are available:

- **Verified** uses requested-version filtering and current/stale-page signals when selecting evidence.
- **Baseline** selects evidence by relevance without those version and authority adjustments. Both modes share the traversal, model settings, prompt caps, and exact-quote validation. This is a project baseline, not a reproduction of another retrieval product or paper.

Quote presence establishes that a passage occurs in the retrieved text. It does not by itself prove that the passage entails the answer. Inspect the quotes and the surrounding source when making a decision.

## Result contract

CLI output and the inspector's JSON download use the same result structure:

| Field | Content |
| --- | --- |
| `answer` | A short factual value or answer; empty for abstention, conflict, or failure. |
| `status` | `answered`, `abstained`, `conflict`, or `failed`. |
| `citations` | Supporting passages, each with `url`, `quote`, `block_id`, and `source_version`. |
| `sources` | Retrieved pages, including `url`, `title`, and detected `version`. |
| `trace` | Navigation and evidence-processing events. |
| `metrics` | Pages, model calls, input/output tokens, and elapsed milliseconds. Unavailable token counts are null; usage_recorded identifies complete usage records. |
| `error` | Failure details when present. |

Version detection is a retrieval aid; an unidentified version is not proof that the page is current. Resource metrics report the coordinator's recorded values, not AMD GPU utilization or an official challenge score.

The local inspector uses `GET /api/health` and `POST /api/query`. A query request contains `question`, `urls`, optional `target_version`, `mode`, and `max_pages`. External page text is evidence data, not executable instructions. The inspector renders returned text as text and restricts clickable source links to HTTP(S).

## Validation and synthetic evaluation

Run the local unit suite:

```powershell
python -m unittest discover -s tests -v
```

The main benchmark contains **16 fictional cases**: eight documentation tasks and eight general website retrieval tasks. They exercise stale pages, unavailable versions, conflicting current sources, tables, conditions, missing answers, and navigation across multiple pages. They are engineering fixtures rather than the organizer's hidden tasks. Model-backed fixture runs use the configured local inference endpoint; the web pages and expected facts remain synthetic. For vLLM runs, set the provider environment above and pass its served name using `--model Qwen3-4B-Instruct-2507` to either benchmark command.

Start with a bounded run:

```powershell
python -m benchmark.run --report-dir work\benchmark-smoke --limit 2 --modes baseline verified
```

Run the complete fixture set when the local model is available for exclusive use:

```powershell
python -m benchmark.run --report-dir work\benchmark-all --modes baseline verified
```

The runner retains output JSON, process logs, `summary.json`, and a human-readable report. It supplies the app with questions and starting URLs, not expected answers. Scoring checks expected status, complete normalized answer aliases, the necessary set of source paths, quote presence, and the page budget. Answer aliases are not a semantic judge; citation block IDs are shape-checked by the benchmark. All failures are retained. See [benchmark/README.md](benchmark/README.md) for the scoring limits.

A separate set adds six synthetic stress-development cases for late code facts, numeric version boundaries, prereleases, conflicts on one page, multiple tables, and absent date/location/eligibility qualifiers. Both modes passed 6/6 in the recorded run. These cases informed fixes and are not held out. See [the stress cases](benchmark/holdout/README.md) and [results](evidence/stress/summary.json). Run them explicitly with:

```powershell
python -m benchmark.holdout.run --run-model --report-dir work\stress --modes baseline verified
```

The actual checks completed for this delivery, including failures and unavailable checks, are recorded in [STATUS.md](STATUS.md) and [DELIVERY.json](DELIVERY.json). Do not infer model or browser validation from a unit-test result.

The repository retains the historical [Ollama synthetic summary](evidence/synthetic/summary.json), [current local unit-test log](evidence/unit-tests.txt), [AMD development evidence](evidence/amd/verification.json), and [package verification record](evidence/package-verification.json). Rerunning the commands above produces fresh evidence for your environment. The original local delivery also had a separate `source-trail-evidence` directory beside the source folder; repository links use the committed `evidence/` snapshot.

## Continuous integration and wheel build

The [CI workflow](.github/workflows/ci.yml) runs the standard-library unit and loopback integration suite on Ubuntu and Windows with Python 3.11 and 3.12. It builds a wheel, installs it into a separate virtual environment, and checks the installed metadata, CLI, inspector HTML, and health endpoint outside the source checkout. CI does not call a live model or run the model-backed benchmark.

Build a wheel locally:

```powershell
python -m pip install build
python -m build --wheel
```

Build tooling is needed only for packaging; the installed coordinator still has no third-party Python runtime dependencies. A successful local check and a passing GitHub workflow are separate results.

## Packaging prototype

`Dockerfile.prototype` packages only the portable Python coordinator and inspector. It supplies neither model weights nor an inference runtime, and it is not the official match submission image.

```powershell
docker build -f Dockerfile.prototype -t source-trail:prototype .
docker run --rm source-trail:prototype --help
```

For model-backed queries inside a container, supply a writable location for output and run the chosen local model runtime in the appropriate network context. The vLLM connector requires a loopback endpoint in that context. The prototype image has not been built or run in the current environment because the local Docker daemon is unavailable. The completed general AMD notebook run does not validate this image against the official environment.

## Current limits

The prototype focuses on readable HTML and plain-text pages. A browser that executes JavaScript, authenticated sessions, PDF extraction, and broader media parsing are outside this first implementation. HTML reading does not reproduce a browser's layout or every CSS visibility rule. A six-page query is deliberately bounded and can miss necessary evidence. Source conflicts and model mistakes still require inspection.

Official Match 4 evaluation still requires the detailed brief, its input/output and runtime contract, validation in the required environment, and the released evaluator. General AMD GPU development validation is complete, and the LabLab project entry is published. Official evaluator results and entry-container compatibility remain unverified.

MIT licensed. Copyright 2026 agammann.

## Recorded development results

The historical local Qwen3.5 Ollama recheck scored verified 14/16 and baseline 12/16. Its verified failures included an unexpected table-answer abstention and comparison wording rejected by strict aliases. The three recorded public queries answered with exact retrieved quotes from [Python TaskGroup documentation](evidence/live-python-taskgroup.json), the [organizer's GPU quota](evidence/live-amd-quota.json), and [FastAPI settings documentation](evidence/live-fastapi-settings.json). The FastAPI citation-deduplication repair and fresh query are recorded in [diagnostics](evidence/diagnostics/live-fastapi-diagnostic-summary.json); its import quotes require surrounding code to establish decorator usage.

The AMD Qwen3-4B-Instruct-2507 run scored **verified 11/16 and baseline 12/16** on the unchanged main fixtures. Both modes scored **6/6** on the stress-development fixtures. The main failures include equivalent full-sentence answers rejected by frozen aliases, two unexpected abstentions despite complete evidence, and a redundant citation in verified mode. All failures are retained in the [AMD main summary](evidence/amd/results/synthetic/summary.json) and [stress summary](evidence/amd/results/stress/summary.json). No aliases or prompts were changed for this run. The different model/runtime prevents a direct comparison with the historical Ollama run, and these development fixtures establish no held-out or official score. See [STATUS.md](STATUS.md) and [DELIVERY.json](DELIVERY.json) for the evidence and remaining requirements.
