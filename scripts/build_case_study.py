"""Build the reviewer-facing single-page case study from validated artifacts."""

# The HTML and CSS template stays inline so the deliverable is one portable page.
# ruff: noqa: E501

from __future__ import annotations

import html
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "runs" / "full-100-20260822-consolidated" / "results.json"
VERIFICATION_PATH = ROOT / "verification" / "manual_sample.json"
OUTPUT_PATH = ROOT / "docs" / "index.html"


def clean_text(value: object) -> str:
    return str(value or "").replace("\u2014", "-").replace("\u2013", "-")


def first_line(value: object) -> str:
    lines = clean_text(value).splitlines()
    return lines[0] if lines else ""


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def build() -> None:
    results = load_json(RESULTS_PATH)
    verification = load_json(VERIFICATION_PATH)
    assert isinstance(results, list)
    assert isinstance(verification, dict)

    category_rows: dict[str, Counter[str]] = defaultdict(Counter)
    auth_counts: Counter[str] = Counter()
    for row in results:
        category_rows[row["category"]][row["buildability"]] += 1
        category_rows[row["category"]]["failed"] += row["status"] == "failed_after_retries"
        if row["status"] != "failed_after_retries":
            auth_counts.update(row["auth"].split("; "))

    category_html = "".join(
        f"""
        <div class="matrix-row">
          <div class="matrix-name">{html.escape(category)}</div>
          <div class="matrix-number yes">{counts["yes"]}</div>
          <div class="matrix-number conditional">{counts["conditional"]}</div>
          <div class="matrix-number unknown">{counts["unknown"]}</div>
          <div class="matrix-number failed">{counts["failed"]}</div>
        </div>"""
        for category, counts in sorted(category_rows.items())
    )

    auth_html = "".join(
        f'<div class="auth-item"><strong>{count}</strong><span>{html.escape(method.replace("_", " ").title())}</span></div>'
        for method, count in auth_counts.most_common()
        if method != "unknown"
    )

    easy_wins = [
        row
        for row in results
        if row["buildability"] == "yes"
        and row["credential_access"] in {"self_serve", "not_required"}
    ]
    easy_names = ", ".join(row["app"] for row in easy_wins[:14])

    failure_rows = [row for row in results if row["status"] == "failed_after_retries"]
    failure_html = "".join(
        f"""
        <article class="failure-item">
          <div><strong>{row["id"]}. {html.escape(row["app"])}</strong><span>{html.escape(row["category"])}</span></div>
          <p>{html.escape(clean_text(row["blocker_or_failure"]).splitlines()[0])}</p>
        </article>"""
        for row in failure_rows
    )

    sample_apps = verification["apps"]
    verification_html = "".join(
        f"""
        <details class="audit-item">
          <summary>
            <span>{app["id"]}. {html.escape(app["app"])}</span>
            <span class="audit-result {app["result"]}">{"Corrected" if app["result"] == "corrected" else "Clean"}</span>
          </summary>
          <p>{html.escape(app["finding"])}</p>
          <a href="{html.escape(app["evidence_url"])}" target="_blank" rel="noreferrer">Official evidence</a>
        </details>"""
        for app in sample_apps
    )

    compact_rows = [
        {
            "id": row["id"],
            "app": clean_text(row["app"]),
            "category": clean_text(row["category"]),
            "status": clean_text(row["status"]),
            "buildability": clean_text(row["buildability"]),
            "auth": clean_text(row["auth"]),
            "access": clean_text(row["credential_access"]),
            "api": clean_text(row["api_availability"]),
            "mcp": clean_text(row["mcp_status"]),
            "blocker": first_line(row["blocker_or_failure"]),
            "evidence": clean_text(row["evidence_urls"]).split(" | ")[0],
        }
        for row in results
    ]
    data_json = json.dumps(compact_rows, ensure_ascii=False).replace("</", "<\\/")

    page = TEMPLATE.replace("{{CATEGORY_ROWS}}", category_html)
    page = page.replace("{{AUTH_ROWS}}", auth_html)
    page = page.replace("{{EASY_COUNT}}", str(len(easy_wins)))
    page = page.replace("{{EASY_NAMES}}", html.escape(easy_names))
    page = page.replace("{{FAILURE_ROWS}}", failure_html)
    page = page.replace("{{VERIFICATION_ROWS}}", verification_html)
    page = page.replace("{{RESULTS_JSON}}", data_json)
    OUTPUT_PATH.write_text(page, encoding="utf-8")


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Evidence-backed research across 100 potential agent integrations.">
  <meta name="theme-color" content="#f6f7f9">
  <title>100 Apps, One Integration Research Agent</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f6f7f9;
      --surface: #ffffff;
      --surface-2: #eceff3;
      --text: #17191d;
      --muted: #646a73;
      --line: #d8dce2;
      --accent: #2457d6;
      --accent-soft: #e6ecff;
      --yes: #0b6b45;
      --conditional: #8a5a00;
      --unknown: #60656e;
      --failed: #9a3030;
      --radius: 12px;
      --max: 1180px;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #111317;
        --surface: #181b20;
        --surface-2: #22262d;
        --text: #f0f2f5;
        --muted: #a8aeb8;
        --line: #343942;
        --accent: #7aa2ff;
        --accent-soft: #1d2b52;
        --yes: #61d6a3;
        --conditional: #efbd62;
        --unknown: #b5bac2;
        --failed: #ff8d8d;
      }
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
    }
    a { color: inherit; }
    button, input, select { font: inherit; }
    .wrap { width: min(calc(100% - 40px), var(--max)); margin: 0 auto; }
    .nav {
      position: sticky;
      top: 0;
      z-index: 5;
      background: color-mix(in srgb, var(--bg) 92%, transparent);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--line);
    }
    .nav-inner { min-height: 62px; display: flex; align-items: center; justify-content: space-between; gap: 24px; }
    .brand { font-weight: 760; letter-spacing: -0.02em; text-decoration: none; white-space: nowrap; }
    .nav-links { display: flex; gap: 20px; font-size: 14px; color: var(--muted); }
    .nav-links a { text-decoration: none; }
    .hero { padding: 76px 0 54px; border-bottom: 1px solid var(--line); }
    .hero-grid { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(280px, .55fr); gap: 64px; align-items: end; }
    .kicker { color: var(--accent); font-weight: 700; font-size: 14px; margin: 0 0 14px; }
    h1 { max-width: 860px; margin: 0; font-size: clamp(46px, 7vw, 88px); letter-spacing: -0.065em; line-height: .96; }
    .hero-copy { max-width: 620px; margin: 24px 0 0; color: var(--muted); font-size: 19px; }
    .hero-note { border-left: 3px solid var(--accent); padding-left: 18px; color: var(--muted); font-size: 15px; }
    .hero-note strong { display: block; color: var(--text); font-size: 24px; margin-bottom: 4px; }
    .metrics { display: grid; grid-template-columns: repeat(4, 1fr); border-bottom: 1px solid var(--line); }
    .metric { padding: 28px 24px; border-right: 1px solid var(--line); }
    .metric:first-child { padding-left: 0; }
    .metric:last-child { border-right: 0; }
    .metric strong { display: block; font-size: 34px; line-height: 1; letter-spacing: -0.04em; }
    .metric span { display: block; margin-top: 8px; color: var(--muted); font-size: 14px; }
    section { padding: 74px 0; border-bottom: 1px solid var(--line); }
    h2 { margin: 0; max-width: 760px; font-size: clamp(32px, 4vw, 52px); letter-spacing: -0.045em; line-height: 1.04; }
    .lead { max-width: 700px; color: var(--muted); font-size: 18px; margin: 18px 0 38px; }
    .finding-grid { display: grid; grid-template-columns: 1.1fr .9fr; gap: 56px; }
    .headline-finding { padding: 26px 0; border-top: 1px solid var(--line); }
    .headline-finding strong { display: block; font-size: 28px; letter-spacing: -0.035em; }
    .headline-finding p { margin: 8px 0 0; color: var(--muted); max-width: 55ch; }
    .auth-panel { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 26px; }
    .auth-panel h3 { margin: 0 0 20px; font-size: 18px; }
    .auth-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1px; background: var(--line); border: 1px solid var(--line); }
    .auth-item { background: var(--surface); padding: 18px; }
    .auth-item strong { display: block; font-size: 27px; }
    .auth-item span { color: var(--muted); font-size: 13px; }
    .matrix { overflow: hidden; border: 1px solid var(--line); border-radius: var(--radius); }
    .matrix-row { display: grid; grid-template-columns: minmax(260px, 1fr) repeat(4, 90px); border-bottom: 1px solid var(--line); }
    .matrix-row:last-child { border-bottom: 0; }
    .matrix-head { background: var(--surface-2); color: var(--muted); font-size: 12px; font-weight: 700; }
    .matrix-name, .matrix-number { padding: 14px 16px; }
    .matrix-number { text-align: center; border-left: 1px solid var(--line); font-variant-numeric: tabular-nums; font-weight: 750; }
    .yes { color: var(--yes); }
    .conditional { color: var(--conditional); }
    .unknown { color: var(--unknown); }
    .failed { color: var(--failed); }
    .opportunity { display: grid; grid-template-columns: 1.15fr .85fr; gap: 24px; }
    .opportunity article { border: 1px solid var(--line); border-radius: var(--radius); padding: 30px; background: var(--surface); }
    .opportunity h3 { margin: 0; font-size: 25px; }
    .opportunity p { color: var(--muted); margin-bottom: 0; }
    .easy-count { font-size: 64px; letter-spacing: -0.06em; line-height: 1; color: var(--accent); margin: 20px 0; }
    .workflow { display: grid; grid-template-columns: repeat(7, 1fr); gap: 10px; }
    .workflow div { min-height: 118px; padding: 16px; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); font-size: 14px; }
    .workflow strong { display: block; margin-bottom: 7px; }
    .workflow span { color: var(--muted); font-size: 12px; }
    .proof { display: grid; grid-template-columns: .8fr 1.2fr; gap: 46px; align-items: start; }
    pre { margin: 0; overflow-x: auto; padding: 22px; background: #15181d; color: #f2f4f7; border-radius: var(--radius); font-size: 13px; }
    .actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 22px; }
    .button { display: inline-flex; align-items: center; min-height: 42px; padding: 0 16px; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 14px; border: 1px solid var(--line); background: var(--surface); }
    .button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
    .verify-summary { display: grid; grid-template-columns: 1fr 1fr 1.2fr; gap: 18px; margin-bottom: 30px; }
    .verify-number { padding: 24px; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); }
    .verify-number strong { display: block; font-size: 38px; letter-spacing: -0.05em; }
    .verify-number span { color: var(--muted); font-size: 14px; }
    .verify-note { padding: 24px; border-left: 3px solid var(--accent); color: var(--muted); }
    .audit-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .audit-item { border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); padding: 0 16px; }
    .audit-item summary { cursor: pointer; display: flex; justify-content: space-between; gap: 12px; padding: 16px 0; font-weight: 700; }
    .audit-item p { color: var(--muted); margin: 0 0 12px; font-size: 14px; }
    .audit-item a { display: inline-block; margin-bottom: 16px; color: var(--accent); font-size: 13px; }
    .audit-result { font-size: 12px; }
    .audit-result.corrected { color: var(--conditional); }
    .audit-result.clean { color: var(--yes); }
    .failure-list { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .failure-item { padding: 18px; border: 1px solid color-mix(in srgb, var(--failed) 35%, var(--line)); border-radius: var(--radius); background: var(--surface); }
    .failure-item div { display: flex; justify-content: space-between; gap: 16px; }
    .failure-item span { color: var(--muted); font-size: 12px; text-align: right; }
    .failure-item p { color: var(--muted); margin: 10px 0 0; font-size: 14px; }
    .controls { display: grid; grid-template-columns: 1fr 220px 180px; gap: 10px; margin: 28px 0 16px; }
    .controls input, .controls select { width: 100%; min-height: 44px; border: 1px solid var(--line); border-radius: 8px; padding: 0 12px; background: var(--surface); color: var(--text); }
    .table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); }
    table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 1000px; }
    th { text-align: left; color: var(--muted); background: var(--surface-2); padding: 12px; position: sticky; top: 62px; }
    td { padding: 12px; border-top: 1px solid var(--line); vertical-align: top; }
    td:first-child, td:nth-child(4) { font-variant-numeric: tabular-nums; }
    .status { font-weight: 700; }
    .evidence-link { color: var(--accent); }
    .empty { display: none; padding: 34px; text-align: center; color: var(--muted); }
    footer { padding: 40px 0 70px; color: var(--muted); font-size: 14px; }
    footer .wrap { display: flex; justify-content: space-between; gap: 20px; }
    @media (max-width: 850px) {
      .nav-links { display: none; }
      .hero-grid, .finding-grid, .opportunity, .proof { grid-template-columns: 1fr; gap: 30px; }
      .metrics { grid-template-columns: 1fr 1fr; }
      .metric { border-bottom: 1px solid var(--line); }
      .metric:nth-child(2) { border-right: 0; }
      .workflow { grid-template-columns: 1fr 1fr; }
      .verify-summary, .audit-grid, .failure-list { grid-template-columns: 1fr; }
      .controls { grid-template-columns: 1fr; }
      .matrix-row { grid-template-columns: minmax(190px, 1fr) repeat(4, 60px); }
      .matrix-name, .matrix-number { padding: 12px 8px; font-size: 12px; }
    }
    @media (max-width: 560px) {
      .wrap { width: min(calc(100% - 28px), var(--max)); }
      .hero { padding-top: 48px; }
      h1 { font-size: 48px; }
      .metrics { grid-template-columns: 1fr; }
      .metric { border-right: 0; padding-left: 0; }
      .workflow { grid-template-columns: 1fr; }
      .matrix { overflow-x: auto; }
      .matrix-row { min-width: 610px; }
      footer .wrap { display: block; }
    }
    @media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }
  </style>
</head>
<body>
  <nav class="nav" aria-label="Case study navigation">
    <div class="wrap nav-inner">
      <a class="brand" href="#top">Integration Research</a>
      <div class="nav-links">
        <a href="#findings">Findings</a><a href="#agent">Agent</a><a href="#verification">Verification</a><a href="#results">100 apps</a>
      </div>
    </div>
  </nav>

  <main id="top">
    <header class="hero">
      <div class="wrap hero-grid">
        <div>
          <p class="kicker">100-app integration research</p>
          <h1>APIs are common. Access is the bottleneck.</h1>
          <p class="hero-copy">An evidence-backed pipeline researched authentication, developer access, API breadth, MCP support and buildability across ten categories.</p>
        </div>
        <div class="hero-note"><strong>92 validated</strong>Eight apps stayed unresolved after bounded retries. Unknown is a result, not a missing row.</div>
      </div>
    </header>

    <div class="wrap metrics" aria-label="Key results">
      <div class="metric"><strong>100</strong><span>apps attempted</span></div>
      <div class="metric"><strong>87</strong><span>documented APIs among 92 completed</span></div>
      <div class="metric"><strong>36</strong><span>confirmed self-serve credential paths</span></div>
      <div class="metric"><strong>103</strong><span>first-pass claims corrected or removed</span></div>
    </div>

    <section id="findings">
      <div class="wrap">
        <h2>The integration surface exists. Production access is harder to prove.</h2>
        <p class="lead">The most useful pattern is operational, not technical: public API documentation is abundant, while credential and production-gate documentation is incomplete.</p>
        <div class="finding-grid">
          <div>
            <div class="headline-finding"><strong>Three auth patterns cover most apps.</strong><p>API keys appear in 40 completed records, OAuth 2.0 in 38 and tokens in 35. Apps often support more than one.</p></div>
            <div class="headline-finding"><strong>47 access paths remain unknown.</strong><p>Only 36 are confirmed self-serve. Seven require a customer administrator and one requires sales contact.</p></div>
            <div class="headline-finding"><strong>Productivity is the clearest entry point.</strong><p>Six of ten are directly buildable and eight have confirmed self-serve access.</p></div>
            <div class="headline-finding"><strong>Support is integration-rich but gated.</strong><p>Six of ten are conditional because of administrator control, app review, enterprise access or early availability.</p></div>
          </div>
          <aside class="auth-panel">
            <h3>Authentication across 92 completed records</h3>
            <div class="auth-list">{{AUTH_ROWS}}</div>
          </aside>
        </div>
      </div>
    </section>

    <section>
      <div class="wrap">
        <h2>Category outcomes</h2>
        <p class="lead">Each row contains ten apps. Unknown includes honest evidence gaps, not assumed negatives. Failed is shown separately and is already included inside Unknown.</p>
        <div class="matrix">
          <div class="matrix-row matrix-head"><div class="matrix-name">Category</div><div class="matrix-number">Yes</div><div class="matrix-number">Conditional</div><div class="matrix-number">Unknown</div><div class="matrix-number">Failed</div></div>
          {{CATEGORY_ROWS}}
        </div>
      </div>
    </section>

    <section>
      <div class="wrap">
        <h2>Easy wins and outreach</h2>
        <p class="lead">Buildability separates a callable surface from the business process required to use it.</p>
        <div class="opportunity">
          <article><h3>Start with self-serve</h3><div class="easy-count">{{EASY_COUNT}}</div><p>Direct buildability plus self-serve or local execution. Representative apps: {{EASY_NAMES}}.</p></article>
          <article><h3>Outreach where access is the product</h3><p>PitchBook needs sales contact. Otter API access is enterprise. NotebookLM requires licences and cloud roles. Google Ads, WhatsApp, Shopify, Intercom, Gorgias and Asana have review gates.</p></article>
        </div>
      </div>
    </section>

    <section id="agent">
      <div class="wrap">
        <h2>A bounded research agent</h2>
        <p class="lead">The model interprets fetched sources. Deterministic code controls discovery, evidence admission, persistence and buildability.</p>
        <div class="workflow" aria-label="Research workflow">
          <div><strong>Catalog</strong><span>100 named apps with identity hints</span></div>
          <div><strong>Search</strong><span>Five role-specific Composio queries</span></div>
          <div><strong>Select</strong><span>Official domains only</span></div>
          <div><strong>Fetch</strong><span>Stored pages and exact excerpts</span></div>
          <div><strong>Extract</strong><span>Structured OpenAI record</span></div>
          <div><strong>Audit</strong><span>Second model checks every claim</span></div>
          <div><strong>Admit</strong><span>Rules compute the final verdict</span></div>
        </div>
      </div>
    </section>

    <section>
      <div class="wrap proof">
        <div>
          <h2>Run the proof</h2>
          <p class="lead">Every app attempt preserves searches, pages, snippets, draft, audit, diff, validation and final output.</p>
          <div class="actions">
            <a class="button primary" href="https://github.com/Anushlinux/research-assignment" target="_blank" rel="noreferrer">Source repository</a>
            <a class="button" href="#results">Inspect results</a>
          </div>
        </div>
        <pre><code>uv sync --frozen

# Run one app
uv run --frozen research run \
  --app-id 61 \
  --run-id github-check

# Run the five-app pilot
uv run --frozen research run \
  --ids 61,22,31,90,98 \
  --run-id pilot</code></pre>
      </div>
    </section>

    <section id="verification">
      <div class="wrap">
        <h2>The first pass was not trusted.</h2>
        <p class="lead">A twelve-app source audit covered all ten categories and compared five material claims per app with stored excerpts from official documentation.</p>
        <div class="verify-summary">
          <div class="verify-number"><strong>52/60</strong><span>first-pass claims matched the supplied evidence</span></div>
          <div class="verify-number"><strong>60/60</strong><span>final sampled claims matched after admission</span></div>
          <div class="verify-note"><strong>Important:</strong> this is sample evidence agreement, not a claimed accuracy score for all 100 apps. Six sampled apps needed correction.</div>
        </div>
        <div class="audit-grid">{{VERIFICATION_ROWS}}</div>
      </div>
    </section>

    <section>
      <div class="wrap">
        <h2>Eight apps defeated the bounded run</h2>
        <p class="lead">Five lacked a catalog-trusted source, two repeatedly failed strict draft validation and one search repeatedly returned a provider error.</p>
        <div class="failure-list">{{FAILURE_ROWS}}</div>
      </div>
    </section>

    <section id="results">
      <div class="wrap">
        <h2>All 100 apps</h2>
        <p class="lead">Search by app, category, auth or blocker. Open the evidence link to inspect the first official source attached to that row.</p>
        <div class="controls">
          <input id="search" type="search" placeholder="Search apps, auth, categories or blockers" aria-label="Search results">
          <select id="category" aria-label="Filter by category"><option value="">All categories</option></select>
          <select id="verdict" aria-label="Filter by verdict"><option value="">All verdicts</option><option value="yes">Yes</option><option value="conditional">Conditional</option><option value="unknown">Unknown</option></select>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>ID</th><th>App</th><th>Category</th><th>Status</th><th>Buildability</th><th>Auth</th><th>Access</th><th>API</th><th>MCP</th><th>Evidence</th></tr></thead>
            <tbody id="rows"></tbody>
          </table>
          <div class="empty" id="empty">No apps match the current filters.</div>
        </div>
      </div>
    </section>
  </main>

  <footer><div class="wrap"><span>Evidence-backed integration research, 2026</span><span>Built with Composio Search, OpenAI structured extraction and deterministic admission.</span></div></footer>

  <script type="application/json" id="research-data">{{RESULTS_JSON}}</script>
  <script>
    const data = JSON.parse(document.getElementById('research-data').textContent);
    const search = document.getElementById('search');
    const category = document.getElementById('category');
    const verdict = document.getElementById('verdict');
    const rows = document.getElementById('rows');
    const empty = document.getElementById('empty');
    const categories = [...new Set(data.map(item => item.category))].sort();
    categories.forEach(value => category.add(new Option(value, value)));

    function escapeText(value) {
      const span = document.createElement('span');
      span.textContent = value || '';
      return span.innerHTML;
    }

    function render() {
      const query = search.value.trim().toLowerCase();
      const filtered = data.filter(item => {
        const haystack = Object.values(item).join(' ').toLowerCase();
        return (!query || haystack.includes(query))
          && (!category.value || item.category === category.value)
          && (!verdict.value || item.buildability === verdict.value);
      });
      rows.innerHTML = filtered.map(item => `
        <tr>
          <td>${item.id}</td><td><strong>${escapeText(item.app)}</strong></td><td>${escapeText(item.category)}</td>
          <td class="status">${escapeText(item.status.replaceAll('_', ' '))}</td>
          <td class="${escapeText(item.buildability)}"><strong>${escapeText(item.buildability)}</strong></td>
          <td>${escapeText(item.auth)}</td><td>${escapeText(item.access.replaceAll('_', ' '))}</td>
          <td>${escapeText(item.api)}</td><td>${escapeText(item.mcp)}</td>
          <td>${item.evidence ? `<a class="evidence-link" href="${encodeURI(item.evidence)}" target="_blank" rel="noreferrer">Open</a>` : escapeText(item.blocker || 'Unresolved')}</td>
        </tr>`).join('');
      empty.style.display = filtered.length ? 'none' : 'block';
    }
    [search, category, verdict].forEach(control => control.addEventListener('input', render));
    render();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    build()
