"""Write the hand-authored, fictional benchmark cases and HTML pages.

This authoring helper is not called by the query app or benchmark runner.
Every factual statement below is synthetic and exists only for local testing.
"""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"
CASES = []


def page(folder, filename, title, body, version=None):
    path = FIXTURES / folder / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    version_meta = f'<meta name="version" content="{version}">' if version else ""
    version_label = f'<p>Documentation version: {version}.</p>' if version else ""
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<title>{title}</title>{version_meta}</head><body>'
        '<header><p>Synthetic benchmark fixture. All organizations, products, '
        'dates, policies, and figures on this page are fictional.</p></header>'
        f'<main><h1>{title}</h1>{version_label}{body}</main></body></html>\n'
    )
    path.write_text(html, encoding="utf-8")


def case(case_id, question, answer, sources, *, status="answered", version=None, aliases=(), category="general"):
    value = {
        "id": case_id,
        "synthetic": True,
        "category": category,
        "question": question,
        "start_path": f"/{case_id}/index.html",
        "expected_answer": answer,
        "expected_status": status,
        "expected_source_paths": [f"/{case_id}/{source}" for source in sources],
        "answer_aliases": list(aliases),
    }
    if version:
        value["target_version"] = version
    CASES.append(value)


def build():
    CASES.clear()
    folder = "01-doc-old-distractor"
    page(folder, "index.html", "AsterQueue documentation", '<p>AsterQueue retry-policy guides:</p><ul><li><a href="v2.html">Version 2 retry policy (archived)</a></li><li><a href="v4.html">Version 4 retry policy (current stable)</a></li></ul>')
    page(folder, "v2.html", "AsterQueue v2 retry policy — archived", '<p>Version 2 uses the fixed retry policy by default.</p><p>This archived release is not the current stable release.</p>', "2")
    page(folder, "v4.html", "AsterQueue v4 retry policy — current stable", '<p>Version 4 uses the adaptive retry policy by default.</p>', "4")
    case(folder, "What is the default retry policy in AsterQueue version 4?", "adaptive", ["v4.html"], version="4", aliases=["adaptive retry policy"], category="documentation")

    folder = "02-doc-target-version-absent"
    page(folder, "index.html", "PebbleStore available documentation", '<p>Only version 3 documentation is published in this fixture.</p><p>No version 5 documentation is available.</p><a href="v3.html">Version 3 connection limits</a>')
    page(folder, "v3.html", "PebbleStore v3 connections", '<p>Version 3 permits 10 simultaneous client connections.</p><p>This page makes no statement about version 5.</p>', "3")
    case(folder, "How many simultaneous client connections does PebbleStore version 5 permit?", "", [], version="5", status="abstained", category="documentation")

    folder = "03-doc-renamed-configuration"
    page(folder, "index.html", "QuartzSite configuration guides", '<ul><li><a href="v2.html">Version 2 cache configuration (archived)</a></li><li><a href="migration-v3.html">Version 3 migration guide</a></li></ul>')
    page(folder, "v2.html", "QuartzSite v2 caching — archived", '<p>Set route_cache to enable route-output caching in version 2.</p>', "2")
    page(folder, "migration-v3.html", "QuartzSite v3 migration — current stable", '<p>In version 3, route_cache was renamed to page_cache. Use page_cache to enable page-output caching.</p><p>The old option route_cache is not accepted in version 3.</p>', "3")
    case(folder, "Which QuartzSite version 3 configuration option replaces route_cache?", "page_cache", ["migration-v3.html"], version="3", category="documentation")

    folder = "04-doc-conditional-default"
    page(folder, "index.html", "LumenServe mode documentation", '<a href="cache-v3.html">Version 3 cache defaults by deployment mode</a>')
    page(folder, "cache-v3.html", "LumenServe v3 cache defaults — current stable", '<p>In development mode, the result cache is enabled by default.</p><p>In production mode with cold starts enabled, the result cache is disabled by default.</p><p>In production mode without cold starts, the result cache is enabled by default.</p>', "3")
    case(folder, "In LumenServe version 3 production mode with cold starts enabled, is the result cache enabled or disabled by default?", "disabled", ["cache-v3.html"], version="3", category="documentation")

    folder = "05-doc-current-stale-release"
    page(folder, "index.html", "CopperFlow worker limits", '<p>The current stable release is version 4.</p><ul><li><a href="v2.html">Worker-limit reference from 2024 (archived version 2)</a></li><li><a href="v4.html">Current stable version 4 worker-limit reference</a></li></ul>')
    page(folder, "v2.html", "CopperFlow v2 limits — archived", '<p>Published 2024-04-01. Version 2 allows a maximum of 6 workers.</p>', "2")
    page(folder, "v4.html", "CopperFlow v4 limits — current stable", '<p>Published 2026-08-01. Version 4 is the current stable release.</p><p>The current stable release allows a maximum of 12 workers.</p>', "4")
    case(folder, "What is the maximum number of workers in the current stable CopperFlow release?", "12 workers", ["v4.html"], aliases=["12"], category="documentation")

    folder = "06-doc-conflicting-current-pages"
    page(folder, "index.html", "CedarRPC version 4 retry references", '<p>Both linked pages describe the current stable version 4. Neither page declares the other superseded.</p><ul><li><a href="reference-v4.html">Current retry reference</a></li><li><a href="guide-v4.html">Current retry setup guide</a></li></ul>')
    page(folder, "reference-v4.html", "CedarRPC v4 retry reference — current stable", '<p>Current version 4 reference, updated 2026-09-01.</p><p>The maximum automatic retry count in version 4 is 3.</p>', "4")
    page(folder, "guide-v4.html", "CedarRPC v4 retry guide — current stable", '<p>Current version 4 guide, updated 2026-09-01.</p><p>The maximum automatic retry count in version 4 is 5.</p>', "4")
    case(folder, "What is the maximum automatic retry count in CedarRPC version 4?", "", ["reference-v4.html", "guide-v4.html"], version="4", status="conflict", category="documentation")

    folder = "07-doc-cross-version-comparison"
    page(folder, "index.html", "FernAPI request quotas", '<ul><li><a href="v2.html">Version 2 quota (archived)</a></li><li><a href="v3.html">Version 3 quota (current stable)</a></li></ul>')
    page(folder, "v2.html", "FernAPI v2 request quota — archived", '<p>The per-client request quota in version 2 is 40 requests per minute.</p>', "2")
    page(folder, "v3.html", "FernAPI v3 request quota — current stable", '<p>The per-client request quota in version 3 is 80 requests per minute.</p>', "3")
    case(folder, "How did the FernAPI per-client request quota change from version 2 to version 3?", "from 40 to 80 requests per minute", ["v2.html", "v3.html"], version="3", aliases=["40 requests per minute to 80 requests per minute", "40 to 80", "doubled from 40", "The per-client request quota increased from 40 requests per minute in version 2 to 80 requests per minute in version 3."], category="documentation")

    folder = "08-doc-prerelease-distractor"
    page(folder, "index.html", "BirchClient release guides", '<p>Version 4 is the current stable release. Version 5 beta is a prerelease.</p><ul><li><a href="v5-beta.html">Version 5 beta timeout guide</a></li><li><a href="v4.html">Version 4 stable timeout guide</a></li></ul>')
    page(folder, "v5-beta.html", "BirchClient v5 beta timeouts — prerelease", '<p>The default request timeout in version 5 beta is 2 seconds.</p><p>This prerelease is not version 4.</p>', "5-beta")
    page(folder, "v4.html", "BirchClient v4 timeouts — current stable", '<p>The default request timeout in version 4 is 8 seconds.</p>', "4")
    case(folder, "What is the default request timeout in BirchClient stable version 4?", "8 seconds", ["v4.html"], version="4", aliases=["eight seconds"], category="documentation")

    folder = "09-web-table-cell"
    page(folder, "index.html", "Amber Bay collection services", '<a href="schedule.html">Collection schedule by material</a>')
    page(folder, "schedule.html", "Amber Bay collection timetable", '<table><thead><tr><th>Material</th><th>Day</th><th>Time</th></tr></thead><tbody><tr><td>Glass</td><td>Every Tuesday</td><td>08:00–10:00</td></tr><tr><td>Electronics</td><td>First Saturday of each month</td><td>09:00–12:00</td></tr><tr><td>Cardboard</td><td>Every Friday</td><td>13:00–15:00</td></tr></tbody></table>')
    case(folder, "On what day and during which hours does Amber Bay collect electronics?", "First Saturday of each month, 09:00–12:00", ["schedule.html"], aliases=["first Saturday 09:00 to 12:00", "first Saturday of each month from 09:00 to 12:00", "first Saturday of each month from 9 am to noon"])

    folder = "10-web-multi-hop-detail"
    page(folder, "index.html", "Mossbridge visitor and permit directory", '<ul><li><a href="parking.html">Parking passes</a></li><li><a href="policies.html">Event-permit policies</a></li></ul>')
    page(folder, "parking.html", "Mossbridge parking passes", '<p>A monthly parking pass costs $14.</p>')
    page(folder, "policies.html", "Mossbridge event-permit policies", '<p>Street-festival application information is in the permit-detail page.</p><a href="festival-detail.html">Street-festival permit fee and application detail</a>')
    page(folder, "festival-detail.html", "Mossbridge street-festival permits", '<p>The application fee for a street-festival permit is $28.</p><p>The fee applies once per application.</p>')
    case(folder, "How much is the Mossbridge street-festival permit application fee?", "$28", ["festival-detail.html"], aliases=["28 dollars", "twenty eight dollars"])

    folder = "11-web-missing-answer"
    page(folder, "index.html", "Cloudberry Theatre ticket help", '<ul><li><a href="refunds.html">Refund conditions</a></li><li><a href="access.html">Venue access</a></li></ul>')
    page(folder, "refunds.html", "Cloudberry Theatre refunds", '<p>All ticket sales are final unless the theatre cancels the performance.</p><p>This fixture does not publish a telephone number.</p>')
    page(folder, "access.html", "Cloudberry Theatre venue access", '<p>The venue entrance opens 30 minutes before each performance.</p>')
    case(folder, "What is the telephone number for Cloudberry Theatre ticket refunds?", "", [], status="abstained")

    folder = "12-web-conflicting-current-hours"
    page(folder, "index.html", "Silver Finch Museum winter hours", '<p>Both linked pages are current for winter 2026 and were updated on the same day. Neither states that the other is superseded.</p><ul><li><a href="hours.html">Visitor opening hours</a></li><li><a href="winter-policy.html">Winter visitor policy</a></li></ul>')
    page(folder, "hours.html", "Silver Finch Museum visitor hours — current", '<p>Updated 2026-09-15. For winter 2026, the museum closes at 17:00 on Sundays.</p>')
    page(folder, "winter-policy.html", "Silver Finch Museum winter policy — current", '<p>Updated 2026-09-15. For winter 2026, the museum closes at 18:00 on Sundays.</p>')
    case(folder, "At what time does Silver Finch Museum close on Sundays in winter 2026?", "", ["hours.html", "winter-policy.html"], status="conflict")

    folder = "13-web-inline-details"
    page(folder, "index.html", "River Lantern Library membership", '<a href="eligibility.html">Digital-card eligibility questions</a>')
    page(folder, "eligibility.html", "River Lantern Library digital cards", '<details open><summary>Who can request a digital card?</summary><p>Residents aged 16 and over can request a digital card.</p></details><details open><summary>Who can request a children’s card?</summary><p>Residents under 16 need a parent or guardian to request a children’s card.</p></details>')
    case(folder, "Who can request a River Lantern Library digital card?", "Residents aged 16 and over", ["eligibility.html"], aliases=["residents age 16 or older", "residents aged 16 or older", "residents aged 16 and above"])

    folder = "14-web-conditional-route"
    page(folder, "index.html", "Wren Island ferry timetable", '<ul><li><a href="south.html">South Dock departures</a></li><li><a href="north.html">North Dock departures</a></li></ul>')
    page(folder, "south.html", "Wren Island South Dock ferry", '<p>The first South Dock weekday ferry departs at 07:10.</p>')
    page(folder, "north.html", "Wren Island North Dock ferry", '<p>The first North Dock weekday ferry departs at 06:20.</p><p>The first North Dock weekend ferry departs at 08:40.</p>')
    case(folder, "When does the first Wren Island ferry leave North Dock on a weekday?", "06:20", ["north.html"], aliases=["6:20 am", "6:20 in the morning"])

    folder = "15-web-effective-date-policy"
    page(folder, "index.html", "Juniper Workshop repair warranties", '<p>The policy effective 2026-07-01 is current; the 2024 policy is archived.</p><ul><li><a href="warranty-2024.html">2024 repair warranty (archived)</a></li><li><a href="warranty-2026.html">Current repair warranty, effective 2026-07-01</a></li></ul>')
    page(folder, "warranty-2024.html", "Juniper Workshop 2024 repair warranty — archived", '<p>Effective 2024-01-01 through 2026-06-30. Completed repairs carry a 30-day warranty.</p>')
    page(folder, "warranty-2026.html", "Juniper Workshop current repair warranty", '<p>Effective 2026-07-01. This policy supersedes the 2024 repair-warranty policy.</p><p>Completed repairs carry a 90-day warranty.</p>')
    case(folder, "Under Juniper Workshop’s current repair policy effective 2026-07-01, how long is the warranty for completed repairs?", "90-day", ["warranty-2026.html"], aliases=["90 days", "ninety days"])

    folder = "16-web-two-source-mapping"
    page(folder, "index.html", "Blue Lantern market vendor permits", '<ul><li><a href="categories.html">Vendor category assignments</a></li><li><a href="fees.html">Daily permit fees by category</a></li></ul>')
    page(folder, "categories.html", "Blue Lantern market vendor categories", '<p>Book vendors are assigned category B.</p><p>Food vendors are assigned category F.</p>')
    page(folder, "fees.html", "Blue Lantern market daily permit fees", '<p>The daily permit fee for category B is $18.</p><p>The daily permit fee for category F is $32.</p>')
    case(folder, "What is the Blue Lantern market daily permit fee for a book vendor?", "$18", ["categories.html", "fees.html"], aliases=["18 dollars", "eighteen dollars"])

    (ROOT / "cases.json").write_text(json.dumps(CASES, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
    print(f"Wrote {len(CASES)} explicitly synthetic cases.")
