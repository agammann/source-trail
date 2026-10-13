# Source Trail synthetic fixture results

All pages and facts in this benchmark are fictional. This is a local engineering check, not an official challenge score.

Model: `qwen3.5:4b-q4_K_M`. Page limit: 6 per query.

Answers must equal a full hand-authored alias after token normalization; no semantic judge is used. Sources must match the exact necessary path set. Quotes must occur in visible fixture text; block IDs are shape-checked only.

| Mode | Passed | Status | Answer aliases | Exact sources | Quotes | Page budget |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 12/16 | 14/16 | 14/16 | 12/16 | 16/16 | 16/16 |
| verified | 14/16 | 15/16 | 14/16 | 15/16 | 16/16 | 16/16 |

## Recorded resource use

| Mode | Pages | Model calls | Input tokens | Output tokens | Duration ms |
| --- | --- | --- | --- | --- | --- |
| baseline | 45 | 16 | 21841 | 744 | 99797 |
| verified | 45 | 15 | 17413 | 709 | 70281 |

## All failures

- `05-doc-current-stale-release` (baseline): source_set_mismatch: missing=[], extra=['/05-doc-current-stale-release/index.html']
- `07-doc-cross-version-comparison` (baseline): status_mismatch: expected answered, got 'failed'; answer_alias_mismatch; source_set_mismatch: missing=['/07-doc-cross-version-comparison/v2.html', '/07-doc-cross-version-comparison/v3.html'], extra=[]; process_exit_code: 1
- `07-doc-cross-version-comparison` (verified): answer_alias_mismatch
- `09-web-table-cell` (baseline): status_mismatch: expected answered, got 'abstained'; answer_alias_mismatch; source_set_mismatch: missing=['/09-web-table-cell/schedule.html'], extra=[]
- `09-web-table-cell` (verified): status_mismatch: expected answered, got 'abstained'; answer_alias_mismatch; source_set_mismatch: missing=['/09-web-table-cell/schedule.html'], extra=[]
- `15-web-effective-date-policy` (baseline): source_set_mismatch: missing=[], extra=['/15-web-effective-date-policy/index.html']
