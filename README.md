# Source Trail

Source Trail retrieves web evidence for a question and makes the answer, supporting quotes, source versions, and navigation path inspectable. It is a local prototype by **agammann**, being prepared for the AMD AI League's web information retrieval match.

The project explores a specific question: can a retrieval workflow handle stale pages, conflicting sources, and missing answers more reliably than a simpler workflow under the same page budget? Its synthetic fixtures provide a way to inspect those cases. They do not establish originality, broad web performance, or a competitive score.

## Challenge status

Checked on **October 12, 2026**: the organizer lists Match 4, *Intelligent Web Information Retrieval*, for October 13–27. Its public description calls for an agent that navigates websites and retrieves specific information from a natural-language request. The Match 4 detail link still opens the overview; a detailed interface, evaluator, runtime contract, and inference rules were not available from that link. See the [official challenge page](https://lablab.ai/ai-hackathons/amd-lablab-ai-academy-challenge).

This implementation precedes the detailed brief. It has not been submitted. AMD GPU execution and an official entry container remain to be verified against the released requirements. The provider connector currently uses local Ollama; it can be adapted to the organizer's permitted local inference runtime once that contract is known.

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

The main benchmark contains **16 fictional cases**: eight documentation tasks and eight general website retrieval tasks. They exercise stale pages, unavailable versions, conflicting current sources, tables, conditions, missing answers, and navigation across multiple pages. They are engineering fixtures rather than the organizer's hidden tasks. Model-backed fixture runs still use the actual local inference endpoint; the web pages and expected facts remain synthetic.

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

The repository retains a curated [synthetic run summary](evidence/synthetic/summary.json), [unit-test log](evidence/unit-tests.txt), and [package verification record](evidence/package-verification.json). These are recorded local checks. Rerunning the commands above produces fresh evidence for your environment. The original local delivery also had a separate `source-trail-evidence` directory beside the source folder; repository links use the committed `evidence/` snapshot.

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

For model-backed queries inside a container, supply an endpoint reachable from that container and a writable location for output. Inference on the target AMD environment must be adapted and tested separately. The prototype image has not been built or run in the current environment because the Docker daemon is unavailable.

## Current limits

The prototype focuses on readable HTML and plain-text pages. A browser that executes JavaScript, authenticated sessions, PDF extraction, and broader media parsing are outside this first implementation. HTML reading does not reproduce a browser's layout or every CSS visibility rule. A six-page query is deliberately bounded and can miss necessary evidence. Source conflicts and model mistakes still require inspection.

Before an entry can be called ready, obtain the Match 4 brief, adapt the input/output and runtime contract, validate on AMD infrastructure, run the released evaluator, and review the resulting submission materials. The challenge entry has not been submitted.

MIT licensed. Copyright 2026 agammann.

## Recorded local result

The latest local recheck scored 14/16 for the verified selection variant and 12/16 for the baseline. The verified failures included an unexpected table-answer abstention and a comparison answer whose wording did not match the strict aliases. Both variants use the same Qwen model and page caps; this is a small development fixture set, not a held-out or official score. Inspect the [recorded summary and failures](evidence/synthetic/summary.json). The latest three public queries answered with exact retrieved quotes from [Python TaskGroup documentation](evidence/live-python-taskgroup.json), the [organizer's GPU quota](evidence/live-amd-quota.json), and [FastAPI settings documentation](evidence/live-fastapi-settings.json). The FastAPI recheck initially failed because repeated exact citations exceeded the raw-list limit; the bounded deduplication repair and a successful fresh query are recorded in [diagnostics](evidence/diagnostics/live-fastapi-diagnostic-summary.json). Its short import quotes require the surrounding code to establish decorator usage. See [STATUS.md](STATUS.md) and [DELIVERY.json](DELIVERY.json) for model, browser, package, and unavailable checks.
