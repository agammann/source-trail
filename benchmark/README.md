# Synthetic local benchmark

The 16 cases contain hand-authored fictional organizations, products, policies,
and figures. Eight exercise documentation retrieval; eight exercise general web
retrieval. These fixtures are an engineering check, not the official challenge
evaluator or evidence of broad web performance.

Run a bounded evaluation from the repository root:

```powershell
python -m benchmark.run --report-dir work\benchmark-smoke --limit 2 --modes baseline verified
```

Run all cases only when the local model is available for exclusive use:

```powershell
python -m benchmark.run --report-dir work\benchmark-all --modes baseline verified
```

The runner starts a loopback fixture server and invokes the public query CLI with
the question, starting URL, optional target version, a six-page limit, and
`--allow-local`. It never supplies expected answers or source lists to the app.
By default, it requests `qwen3.5:4b-q4_K_M`. `--timeout`, `--model`, and
`--max-pages` can override those run constraints.

Each report directory retains app output JSON, process stdout/stderr, a running
`summary.json`, and `report.md`. All status, answer, citation, schema, page-budget,
and process failures are reported. Reusing a report directory overwrites output
for the selected cases and modes.

Scoring requires the expected status, an exact full answer alias for answered cases, the
exact set of necessary supporting source paths, and quotes present in visible
fixture text. After case and punctuation normalization, the entire answer token
sequence must equal one explicit alias. Extra explanations, alternatives,
negations, and unlisted unit substitutions do not pass. This is a heuristic,
not a semantic judge. The query should return a short value-only answer.
Inline HTML is whitespace-normalized and
tables use visible row separators. Citation block IDs are shape-checked only;
the evaluator does not establish that a block ID binds to its quote. Resource
counts are the app's recorded metrics. Tokens and model calls are reported;
the configured hard check is the page limit, plus the process timeout.

The multi-page version-comparison case intentionally needs both old and new
documentation as evidence. The two conflict cases intentionally have current
sources with incompatible facts and no stated authority order. Abstentions have
no supporting answer source.

During development, review of the first complete model run identified two valid
answer forms rejected by the initial aliases. Case 01 now also accepts the full
answer `adaptive retry policy`, which restates the version 4 fixture’s adaptive
default. Case 07 now also accepts the full sentence `The per-client request quota
increased from 40 requests per minute in version 2 to 80 requests per minute in
version 3.`, which preserves both version assignments, values, and units.
These are development-rubric adjustments made after inspecting development
outputs. They are not a holdout evaluation or independent generalization result.
Matching still requires a complete alias; alternatives, wrong version
assignments, changed units, and contradictory answers do not pass. Status and
citation checks remain in force, including the first-run baseline case 07’s
genuine failure when its generated quote did not exactly match retrieved text.

The checked-in pages can be regenerated from the hand-authored fixture source:

```powershell
python -m benchmark.build_fixtures
python -m unittest discover -s tests -p test_benchmark.py -v
```
