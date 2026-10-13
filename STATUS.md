# Source Trail status

Checked October 12, 2026. This is a local prototype for AMD AI League Match 4, Intelligent Web Information Retrieval, scheduled October 13–27. The detailed contract is still unavailable from the public Match 4 link.

| Check | Recorded result |
| --- | --- |
| Unit and integration suite | 93/93 passed, including real loopback HTTP and provider stubs. |
| Main synthetic development set | Verified 14/16; baseline 12/16. All output, scoring failures, and resource records are committed. |
| Separate synthetic stress-development set | Both modes 6/6 with actual local Qwen inference. Cases informed fixes; not held out. |
| Completed-response replay | Final validator accepted 46 saved completed responses; no new inference in this replay. |
| Public websites | Three latest queries answered: Python TaskGroup, organizer GPU quota, FastAPI settings. Quotes match retrieved blocks. |
| Browser | Prior desktop/mobile interaction checks passed. Final-source example filling, live query, quotes, navigation, JSON download and console checks passed. |
| Python packaging | Final wheel build and isolated installed metadata/CLI/HTML/HTTP/health smoke passed. |
| Windows launcher | Interpreter discovery, explicit and relative paths, start from another directory, and health request passed. |
| GitHub | Source published. All four Ubuntu/Windows and Python 3.11/3.12 CI jobs passed; see evidence/github-ci.json. |
| Docker | Not run: local daemon unavailable. Dockerfile.prototype packages only the coordinator. |
| AMD notebook | Approved sign-in completed; dashboard reported the account email was not registered for this hackathon. No GPU session launched. |
| Official evaluator | Not available or run; no submission made. |

The verified main-set failures were an unexpected refusal on complete table evidence and a correct cross-version answer whose wording did not match the strict complete-answer aliases. The baseline also supplied extra unnecessary sources on current-release and effective-date cases. No aliases were changed for this recheck.

The FastAPI live query initially failed because the model repeated twelve exact citations that represented two distinct source-and-quote pairs. Every proposed quote is now checked before deduplication, with a bounded raw list and at most ten distinct citations. A fresh live query succeeded after the repair. The failed output and recorded diagnostic response remain in evidence/.

These are engineering checks on a small development corpus. They do not establish broad web performance or an official score. Model ordering and warm-up affect recorded duration; no speed advantage is claimed. An exact quote establishes text integrity, not answer entailment. In particular, the FastAPI import quotes need the surrounding code to establish decorator usage.

The implementation supports static HTML and plain text, up to the configured page/evidence limits. JavaScript browser navigation, authenticated sources, PDFs, and media remain outside its scope. Version markers are heuristic, and requested versions require identifiable matching context.

Next: obtain the released Match 4 contract, adapt the interface and permitted inference runtime, resolve notebook registration, validate on AMD infrastructure and the official evaluator, then review the completed entry before submission.
