# AMD development validation

On October 13, 2026, the general AMD One-Click Tutorial service provided one AMD Instinct MI300X virtual function. Source Trail revision `7e406424b14ce49a77352111c51f5ae7980df4f0` ran with local vLLM and pinned Qwen3-4B-Instruct-2507 weights. The [verification record](verification.json) contains runtime versions, source hashes and evidence references.

- **114/114 unit and loopback tests passed** in the AMD environment. Unit tests use fixtures and provider stubs.
- The fresh [Python TaskGroup query](results/live-python-taskgroup.json) answered with one exact supporting quote, including the exception qualifier excluding `asyncio.CancelledError`.
- The unchanged [main synthetic suite](results/synthetic/summary.json) scored **baseline 12/16, verified 11/16**.
- The [stress-development suite](results/stress/summary.json) scored **6/6 in both modes**.

All 44 recorded model requests completed with HTTP 200 and `finish_reason=stop`. Raw provider usage, application totals and server metrics agree at **58,604 input tokens and 2,335 output tokens**. Each request interval overlaps active GPU telemetry. The 101 successful samples include 96 with nonzero graphics utilization. This establishes actual inference in this environment; the sampled activity is not a performance benchmark.

The recording relay in [validate.py](validate.py) forwards each application request unchanged to the loopback vLLM server, stores its request and response, and returns the original response bytes to the connector. [Provider records](results/provider/request-001.json), [server log](vllm-server.log), [metric snapshots](results/server-metrics-after.txt), [GPU activity](results/gpu-activity.json) and [run manifest](results/validation.json) allow the run to be inspected. The relay does not add expected answers to prompts.

Rescoring reproduced all 44 saved case scores. Two equivalent full-sentence answers fail the frozen aliases; two tasks abstain despite complete evidence; verified mode also adds one redundant current-policy citation. All failures remain in the summaries and per-case outputs. Aliases, prompts and fixture content were unchanged. These development cases are not held out, and this run does not show a verified-mode improvement over its baseline.

The historical Qwen3.5/Ollama results elsewhere in the repository use a different model/runtime. These records do not establish official Match 4 registration, container compatibility or evaluator success. The currently public details link returns the overview and the visible starter kit is for Match 3.

Public curation omits unneeded device identifiers, session names and one distributed-initialization network line. Provider requests, responses, scores and totals are unchanged. Exact quotes establish retrieved-text integrity; answer applicability still requires source inspection.
