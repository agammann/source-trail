# Separate synthetic stress-development corpus

These six cases were created separately from the earlier 16-case corpus. Their
fictional facts and pages had not been used in the previous model runs when
written. The deterministic probes inspect implementation boundaries and are
being used to inform fixes, so this suite is classified **stress-development**.
The directory name is not a held-out evaluation claim. Any later prompt, code,
or rubric changes based on these cases remain development work.

The cases cover a fact late in a long `pre`/`code` block, v4 versus v40, v4 versus
an unseparated v4beta tag, incompatible current values on one page, identical
table columns under different sections, and a qualified question whose source
omits the requested location, eligibility, and year. Expected facts reside in
`cases.json`; application calls receive only question, start URL, and optional
target version. The fixture author has not run an inference model on this set.

Run deterministic retrieval/selection/validation tests:

```powershell
python -m unittest discover -s tests -p test_holdout.py -v
```

The tests retrieve fictional pages through a stdlib loopback HTTP server. They
do not contact Ollama, call an inference model, or access external websites.
Tests describing desired behavior may initially fail where the implementation
does not yet support it. Such failures must be reported or repaired before
representing those behaviors as supported.

An optional model runner is available for the coordinating task. Its explicit
switch prevents accidental inference during deterministic fixture checks:

```powershell
python -m benchmark.holdout.run --run-model --report-dir work/stress-development --modes baseline verified
```

Reports retain the stress-development classification, exact alias scoring,
source and quote checks, budgets, every failure, and the application’s error
when present. They do not establish broad retrieval quality or challenge scores.

Regenerate the checked-in fictional pages and facts with:

```powershell
python -m benchmark.holdout.build_fixtures
```
