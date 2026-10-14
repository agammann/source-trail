# Source Trail synthetic fixture results

All pages and facts in this benchmark are fictional. This is a local engineering check, not an official challenge score.

Model: `Qwen3-4B-Instruct-2507`. Page limit: 6 per query.

Answers must equal a full hand-authored alias after token normalization; no semantic judge is used. Sources must match the exact necessary path set. Quotes must occur in visible fixture text; block IDs are shape-checked only.

| Mode | Passed | Status | Answer aliases | Exact sources | Quotes | Page budget |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 12/16 | 14/16 | 12/16 | 14/16 | 16/16 | 16/16 |
| verified | 11/16 | 14/16 | 12/16 | 13/16 | 16/16 | 16/16 |

## Recorded resource use

| Mode | Pages | Model calls | Input tokens | Output tokens | Duration ms |
| --- | --- | --- | --- | --- | --- |
| baseline | 45 | 16 | 21835 | 835 | 10809 |
| verified | 45 | 15 | 17389 | 845 | 10885 |

## All failures

- `09-web-table-cell` (baseline): answer_alias_mismatch
- `09-web-table-cell` (verified): answer_alias_mismatch
- `10-web-multi-hop-detail` (baseline): status_mismatch: expected answered, got 'abstained'; answer_alias_mismatch; source_set_mismatch: missing=['/10-web-multi-hop-detail/festival-detail.html'], extra=[]
- `10-web-multi-hop-detail` (verified): status_mismatch: expected answered, got 'abstained'; answer_alias_mismatch; source_set_mismatch: missing=['/10-web-multi-hop-detail/festival-detail.html'], extra=[]
- `13-web-inline-details` (baseline): answer_alias_mismatch
- `13-web-inline-details` (verified): answer_alias_mismatch
- `15-web-effective-date-policy` (verified): source_set_mismatch: missing=[], extra=['/15-web-effective-date-policy/index.html']
- `16-web-two-source-mapping` (baseline): status_mismatch: expected answered, got 'abstained'; answer_alias_mismatch; source_set_mismatch: missing=['/16-web-two-source-mapping/categories.html', '/16-web-two-source-mapping/fees.html'], extra=[]
- `16-web-two-source-mapping` (verified): status_mismatch: expected answered, got 'abstained'; answer_alias_mismatch; source_set_mismatch: missing=['/16-web-two-source-mapping/categories.html', '/16-web-two-source-mapping/fees.html'], extra=[]
