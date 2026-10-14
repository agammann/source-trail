# Source Trail status

Checked October 13, 2026 locally. The [LabLab project entry](https://lablab.ai/ai-hackathons/amd-lablab-ai-academy-challenge/ammann-labs/source-trail) is published under Ammann Labs; its public page displays October 14. Submission confirmation and public fields were verified at 2026-10-14 04:45:39 UTC; see [the receipt](evidence/lablab-submission.json). This prototype has completed a specific AMD GPU development run for AMD AI League Match 4, Intelligent Web Information Retrieval, now listed as live for October 13–27. The detailed contract is still unavailable from the public Match 4 link, which returns the overview; the visible starter kit is labeled Match 3.

| Check | Recorded result |
| --- | --- |
| Unit and integration suite | 114/114 passed locally and in the AMD notebook, including real loopback HTTP, both provider connectors, and browser configuration boundaries. |
| Historical Ollama development set | Verified 14/16; baseline 12/16 with Qwen3.5. Output, scoring failures and resource records remain committed. |
| AMD main synthetic development set | Verified 11/16; baseline 12/16 with Qwen3-4B-Instruct-2507 and local vLLM. Frozen scoring and all failures retained. |
| Separate synthetic stress-development set | Both modes 6/6 in the historical Ollama and fresh AMD runs. Cases informed fixes; not held out. |
| Completed-response replay | Final validator accepted 46 saved completed responses; no new inference in this replay. |
| Public websites | Historical TaskGroup, organizer quota and FastAPI queries retained. Fresh AMD TaskGroup query answered with an exact quote preserving the exception qualifier. |
| Browser | Prior desktop/mobile interaction checks passed. Final-source example filling, live query, quotes, navigation, JSON download and console checks passed. |
| Python packaging | Final audit wheel build and isolated installed metadata/CLI/HTML/HTTP/health smoke passed. |
| Windows launcher | Interpreter discovery, explicit and relative paths, start from another directory, and health request passed. |
| GitHub | Source published. All four Ubuntu/Windows and Python 3.11/3.12 jobs passed for the vLLM code revision; see evidence/github-ci.json. |
| LabLab submission | Successfully submitted under Ammann Labs; public title, team, repository, description and tags verified. See evidence/lablab-submission.json. |
| Docker | Not run: local daemon unavailable. Dockerfile.prototype packages only the coordinator. |
| General AMD notebook | One-Click Tutorial launched an MI300X virtual function. Local vLLM completed 44 model requests; provider usage, server metrics and generation-time GPU activity agree. See evidence/amd/verification.json. |
| Hackathon notebook route | Earlier signed-in /hackathon dashboard reported the account email was not registered. Registration with AMD's hackathon notebook route remains unverified; the published LabLab entry is a separate record. No Discord note sent. |
| Official evaluator | Not available or run; no official Match 4 score verified. |

The submitted source snapshot is `babe608e31d5f672baf27550487102ba6a06f550`, and the AMD runtime source is `7e406424b14ce49a77352111c51f5ae7980df4f0`. Existing source and evidence ZIPs, the manifest and the wheel retain the submitted snapshot. This receipt/documentation update does not rebuild or replace them.

The later audit repaired prerelease-to-stable comparisons, adjacent-table column context, and block markup inside table cells. Fresh loopback acquisition and selection reproduced all 44 saved main/stress evidence inputs with zero model calls; see evidence/evidence-selection-recheck.json.

The vLLM connector uses the same evidence prompt and final quote/version checks as Ollama. Its local endpoint stays on loopback, optional authentication stays in operator configuration, and incomplete or malformed completions are rejected. Token counts remain unavailable when absent; supplied counts and totals are checked. The browser cannot select the endpoint, provider or model.

The fresh AMD run used source revision 7e406424b14ce49a77352111c51f5ae7980df4f0, one AMD Instinct MI300X VF, pinned Qwen3-4B-Instruct-2507 weights, and the recorded ROCm/PyTorch/vLLM runtime. All 44 HTTP responses completed with stop; raw provider usage, application totals and server metric deltas agree at 58,604 input and 2,335 output tokens. Each request overlapped active GPU samples. The 101 samples include 96 with nonzero graphics utilization. These records establish actual inference in that specific environment and are not a GPU performance comparison.

Independent rescoring reproduced every frozen AMD score. The main failures include equivalent sentences rejected by exact aliases, two model abstentions despite complete evidence, and a redundant current-policy citation in verified mode. No retrieval or connector defect was found in these failures. No aliases or prompts were changed. This run does not show a verified-mode improvement over its baseline. The historical Ollama scores use a different model/runtime and remain separate.

In the historical Ollama recheck, the verified main-set failures were an unexpected refusal on complete table evidence and a correct cross-version answer whose wording did not match the strict complete-answer aliases. That baseline also supplied extra unnecessary sources on current-release and effective-date cases. No aliases were changed for that recheck.

The FastAPI live query initially failed because the model repeated twelve exact citations that represented two distinct source-and-quote pairs. Every proposed quote is now checked before deduplication, with a bounded raw list and at most ten distinct citations. A fresh live query succeeded after the repair. The failed output and recorded diagnostic response remain in evidence/.

These are engineering checks on a small development corpus. They do not establish broad web performance or an official score. Model ordering and warm-up affect recorded duration; no speed advantage is claimed. An exact quote establishes text integrity, not answer entailment. In particular, the FastAPI import quotes need the surrounding code to establish decorator usage.

The implementation supports static HTML and plain text, up to the configured page/evidence limits. JavaScript browser navigation, authenticated sources, PDFs, and media remain outside its scope. Version markers are heuristic, and requested versions require identifiable matching context.

Remaining official-evaluation work: obtain the detailed Match 4 contract, adapt its interface and permitted runtime, establish access to that required environment, and run its evaluator. The local prototype, general AMD GPU development validation, public source delivery and LabLab project submission are complete. Publication of the entry does not establish official evaluator compatibility or a competitive score.
