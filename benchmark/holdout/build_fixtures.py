"""Author the separate fictional stress corpus, without invoking inference."""

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASES = []


def page(folder, filename, title, body, version=None):
    destination = HERE / "fixtures" / folder / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    version_text = f"<p>Documentation version: {version}.</p>" if version else ""
    destination.write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<title>{title}</title></head><body><header><p>Synthetic stress-development fixture. '
        'All products, organizations, policies, dates, and figures are fictional.</p></header>'
        f'<main><h1>{title}</h1>{version_text}{body}</main></body></html>\n',
        encoding="utf-8",
    )


def case(identifier, question, answer, sources, *, status="answered", version=None, aliases=(), **probes):
    record = {
        "id": identifier, "synthetic": True, "classification": "stress-development",
        "question": question, "start_path": f"/{identifier}/index.html",
        "expected_answer": answer, "answer_aliases": list(aliases),
        "expected_status": status,
        "expected_source_paths": [f"/{identifier}/{filename}" for filename in sources],
        **probes,
    }
    if version:
        record["target_version"] = version
    CASES.append(record)


def build():
    CASES.clear()
    identifier = "h01-late-code-fact"
    page(identifier, "index.html", "HemlockSync guide directory", '<a href="v6.html">Version 6 digest-window configuration</a>')
    # A genuine long block: the fact is after 3,900 characters, not in a caption.
    prefix = "\n".join(f'reserved_flag_{number:03d} = "unset"' for number in range(1, 151))
    quote = 'digest_window = "36 hours"'
    page(identifier, "v6.html", "HemlockSync v6 digest configuration", f"<p>The following code block is the published default configuration.</p><pre><code>{prefix}\n{quote}\n</code></pre>", "6")
    case(identifier, "What is the configured digest_window in HemlockSync version 6?", "36 hours", ["v6.html"], version="6", required_evidence_quotes=[quote])

    identifier = "h02-numeric-version-suffix"
    page(identifier, "index.html", "SableBuffer storage-guide directory", '<ul><li><a href="v40.html">Version 40 storage allowance</a></li><li><a href="v4.html">Version 4 storage allowance</a></li></ul>')
    page(identifier, "v40.html", "SableBuffer v40 storage allowance", '<p>The per-workspace storage allowance in version 40 is 1200 MiB.</p>', "40")
    page(identifier, "v4.html", "SableBuffer v4 storage allowance", '<p>The per-workspace storage allowance in version 4 is 96 MiB.</p>', "4")
    case(identifier, "What is the per-workspace SableBuffer storage allowance in version 4?", "96 MiB", ["v4.html"], version="4", aliases=["96 mebibytes"], excluded_evidence_paths=[f"/{identifier}/v40.html"])

    identifier = "h03-unseparated-prerelease"
    page(identifier, "index.html", "JuncoMail acknowledgement-guide directory", '<ul><li><a href="v4beta.html">Version 4beta acknowledgement timeout</a></li><li><a href="v4.html">Version 4 acknowledgement timeout</a></li></ul>')
    page(identifier, "v4beta.html", "JuncoMail v4beta delivery acknowledgement", '<p>This is a prerelease preview of version 4beta, not stable version 4.</p><p>The delivery acknowledgement timeout in version 4beta is 2 seconds.</p>', "4beta")
    page(identifier, "v4.html", "JuncoMail v4 delivery acknowledgement", '<p>Version 4 is the current stable release.</p><p>The delivery acknowledgement timeout in version 4 is 11 seconds.</p>', "4")
    case(identifier, "In JuncoMail version 4, what is the delivery acknowledgement timeout?", "11 seconds", ["v4.html"], version="4", aliases=["eleven seconds"], excluded_evidence_paths=[f"/{identifier}/v4beta.html"])

    identifier = "h04-same-page-conflict"
    first = "The maximum concurrency for a standard MeadowTask workspace is 14 jobs."
    second = "The maximum concurrency for a standard MeadowTask workspace is 21 jobs."
    page(identifier, "index.html", "MeadowTask current standard-workspace concurrency", '<p>Both statements below apply to the same standard workspace and the same current service plan. Neither section supersedes the other.</p><h2>Reference limit</h2>' + f"<p>{first}</p><h2>Setup limit</h2><p>{second}</p>")
    case(identifier, "What is the current maximum concurrency for a standard MeadowTask workspace?", "", ["index.html"], status="conflict", incompatible_quotes=[first, second])

    identifier = "h05-multiple-table-context"
    page(identifier, "index.html", "Turnstone Hall access limits", '<h2>Guest entry limits</h2><p>The venue counts guest admissions at the main door.</p><table><tr><th>Plan</th><th>Maximum entries</th></tr><tr><td>Studio</td><td>6 entries</td></tr><tr><td>Gallery</td><td>18 entries</td></tr></table><h2>Operator entry limits</h2><p>The venue counts entries at the east door.</p><table><tr><th>Plan</th><th>Maximum entries</th></tr><tr><td>Studio</td><td>12 entries</td></tr><tr><td>Gallery</td><td>24 entries</td></tr></table>')
    case(identifier, "What is the operator entry limit for Turnstone Hall’s Studio plan?", "12 entries", ["index.html"], aliases=["12"], table_quote="Studio | 12 entries", required_table_section="Operator entry limits", required_table_header="Plan | Maximum entries")

    identifier = "h06-missing-query-qualifiers"
    page(identifier, "index.html", "Docklight Museum membership directory", '<a href="membership.html">Listed general monthly membership price</a>')
    page(identifier, "membership.html", "Docklight Museum general membership", '<p>The listed general monthly membership price is $22.</p><p>This page supplies no pricing eligibility rules and no effective date.</p>')
    case(identifier, "What monthly Docklight Museum membership price applies to Quail County resident students in 2027?", "", [], status="abstained", missing_qualifiers=["Quail County", "resident students", "2027"], unqualified_quote="The listed general monthly membership price is $22.")

    (HERE / "cases.json").write_text(json.dumps(CASES, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
    print(f"Wrote {len(CASES)} separate synthetic stress-development cases.")
