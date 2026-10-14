# Source Trail status

Checked October 13, 2026 locally. The [LabLab project entry](https://lablab.ai/ai-hackathons/amd-lablab-ai-academy-challenge/ammann-labs/source-trail) is published under Ammann Labs; its public page displays October 14. Submission confirmation and public fields were verified at 2026-10-14 04:45:39 UTC; see [the receipt](evidence/lablab-submission.json). This prototype has completed a specific AMD GPU development run for AMD AI League Match 4, Intelligent Web Information Retrieval, now listed as live for October 13–27. Common container rules are available in the organizer's infrastructure PDF, but its task interface is OCR. The Match 4 interface and evaluator remain unavailable; see [the contract review](docs/official-match4-status.md).

| Check | Recorded result |
| --- | --- |
| Unit and integration suite | 114/114 passed locally and in the AMD notebook, including real loopback HTTP, both provider connectors, and browser configuration boundaries. |
| Supplemental extractive demo | 24/24 focused tests passed alongside a fresh 114/114 core run. The AMD-tested core hashes are unchanged. Two fresh browser queries answered with exact passages; source/version and navigation disclosures and JSON download passed. Mobile width stayed within 390 pixels. See evidence/demo/local-checks.json. |
| Public online demo | Free https://source-trail.streamlit.app/ deployed from demo/app.py using Python 3.12.15, Streamlit 1.65.0 and pinned Ollama 0.40.3. Public visibility was checked. TaskGroup and MIT-license questions both answered with fresh retrieval and one model call each; quotes, source/trace disclosures and JSON downloads passed. See evidence/demo/cloud-checks.json. Free hosting can sleep/restart; no uptime or general quality claim. |
| Submission media | Published MP4 (118.9 seconds, 2.74 MB), six-page PDF, editable six-slide PPTX and PNG cover (2560 × 1440). Full audio/video decode and visual checks passed. All four public asset digests and sizes match local files; see evidence/media-release.json and evidence/media-qa.json. |
| Historical Ollama development set | Verified 14/16; baseline 12/16 with Qwen3.5. Output, scoring failures and resource records remain committed. |
| AMD main synthetic development set | Verified 11/16; baseline 12/16 with Qwen3-4B-Instruct-2507 and local vLLM. Frozen scoring and all failures retained. |
| Separate synthetic stress-development set | Both modes 6/6 in the historical Ollama and fresh AMD runs. Cases informed fixes; not held out. |
| Completed-response replay | Final validator accepted 46 saved completed responses; no new inference in this replay. |
| Public websites | Historical TaskGroup, organizer quota and FastAPI queries retained. Fresh AMD TaskGroup query answered with an exact quote preserving the exception qualifier. |
| Browser | Prior desktop/mobile interaction checks passed. Final-source example filling, live query, quotes, navigation, JSON download and console checks passed. |
| Python packaging | Final audit wheel build and isolated installed metadata/CLI/HTML/HTTP/health smoke passed. |
| Windows launcher | Interpreter discovery, explicit and relative paths, start from another directory, and health request passed. |
| GitHub | Source published. All four Ubuntu/Windows and Python 3.11/3.12 jobs passed for the vLLM code revision; see evidence/github-ci.json. |
| Supplemental demo CI | All four Ubuntu/Windows and Python 3.11/3.12 jobs passed for b558b7b, with 114 core tests, 24 demo tests and isolated installed-package checks in each job. See evidence/demo/github-ci.json. |
| LabLab submission | Successfully submitted under Ammann Labs; public title, team, repository, description and tags verified. See evidence/lablab-submission.json. |
| Docker | Not run: local daemon unavailable. Dockerfile.prototype packages only the coordinator. |
| General AMD notebook | One-Click Tutorial launched an MI300X virtual function. Local vLLM completed 44 model requests; provider usage, server metrics and generation-time GPU activity agree. See evidence/amd/verification.json. |
| Hackathon notebook route | Rechecked signed-in /hackathon dashboard October 13: it still reports the account email is not registered for the hackathon. Dedicated-pool access is blocked; the published LabLab entry is a separate record. No Discord note sent. |
| Official evaluator | Not available or run; no official Match 4 score verified. |

The submitted source snapshot is `babe608e31d5f672baf27550487102ba6a06f550`, and the AMD runtime source is `7e406424b14ce49a77352111c51f5ae7980df4f0`. Existing source and evidence ZIPs, the manifest and the wheel retain the submitted snapshot. Supplemental demo and documentation updates do not rebuild or replace them.

The supplemental demo uses Qwen3 0.6B with a separate single-passage selection prompt. It copies the selected passage verbatim and passes it through the existing validator. It is not the AMD answer prompt, has not been benchmarked against the AMD set, and cannot establish version comparisons or synthesize across sources. Three initial attempts with the original answer prompt abstained; their results are retained alongside two successful extractive requests. The README-license attempt also exposed a lexical-selection limitation in the unchanged core. The direct-license document was successfully queried after switching the demo prompt. These checks do not establish general retrieval quality.

The later audit repaired prerelease-to-stable comparisons, adjacent-table column context, and block markup inside table cells. Fresh loopback acquisition and selection reproduced all 44 saved main/stress evidence inputs with zero model calls; see evidence/evidence-selection-recheck.json.

The vLLM connector uses the same evidence prompt and final quote/version checks as Ollama. Its local endpoint stays on loopback, optional authentication stays in operator configuration, and incomplete or malformed completions are rejected. Token counts remain unavailable when absent; supplied counts and totals are checked. The browser cannot select the endpoint, provider or model.

The fresh AMD run used source revision 7e406424b14ce49a77352111c51f5ae7980df4f0, one AMD Instinct MI300X VF, pinned Qwen3-4B-Instruct-2507 weights, and the recorded ROCm/PyTorch/vLLM runtime. All 44 HTTP responses completed with stop; raw provider usage, application totals and server metric deltas agree at 58,604 input and 2,335 output tokens. Each request overlapped active GPU samples. The 101 samples include 96 with nonzero graphics utilization. These records establish actual inference in that specific environment and are not a GPU performance comparison.

Independent rescoring reproduced every frozen AMD score. The main failures include equivalent sentences rejected by exact aliases, two model abstentions despite complete evidence, and a redundant current-policy citation in verified mode. No retrieval or connector defect was found in these failures. No aliases or prompts were changed. This run does not show a verified-mode improvement over its baseline. The historical Ollama scores use a different model/runtime and remain separate.

In the historical Ollama recheck, the verified main-set failures were an unexpected refusal on complete table evidence and a correct cross-version answer whose wording did not match the strict complete-answer aliases. That baseline also supplied extra unnecessary sources on current-release and effective-date cases. No aliases were changed for that recheck.

The FastAPI live query initially failed because the model repeated twelve exact citations that represented two distinct source-and-quote pairs. Every proposed quote is now checked before deduplication, with a bounded raw list and at most ten distinct citations. A fresh live query succeeded after the repair. The failed output and recorded diagnostic response remain in evidence/.

These are engineering checks on a small development corpus. They do not establish broad web performance or an official score. Model ordering and warm-up affect recorded duration; no speed advantage is claimed. An exact quote establishes text integrity, not answer entailment. In particular, the FastAPI import quotes need the surrounding code to establish decorator usage.

The implementation supports static HTML and plain text, up to the configured page/evidence limits. JavaScript browser navigation, authenticated sources, PDFs, and media remain outside its scope. Version markers are heuristic, and requested versions require identifiable matching context.

The general LabLab requirements include a 16:9 cover, MP4 video, PDF presentation and a working online application. The AMD form did not expose all those fields, and no waiver was found. These supplemental media are now publicly downloadable, and the online demo completed actual hosted queries. Links are being added to the existing entry through its Additional Information field.

Remaining official-evaluation work: obtain the Match 4 task interface, adapt it to the prescribed common container base, establish access to that environment, and run its evaluator. The tutorial run used ROCm 7.14/PyTorch 2.11, differing from the required base. Publication of the entry does not establish official evaluator compatibility or a competitive score.
