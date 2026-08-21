"""Build the reviewer-facing single-page case study from validated artifacts."""

# The HTML and CSS remain inline so the deliverable is one portable page.
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


def clean(value: object) -> str:
    return str(value or "").replace("\u2014", "-").replace("\u2013", "-")


def esc(value: object) -> str:
    return html.escape(clean(value))


def first_line(value: object) -> str:
    lines = clean(value).splitlines()
    return lines[0] if lines else ""


def build() -> None:
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    verification = json.loads(VERIFICATION_PATH.read_text(encoding="utf-8"))

    categories: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: {"build": Counter(), "access": Counter()}
    )
    auth_counts: Counter[str] = Counter()
    for row in results:
        categories[row["category"]]["build"][row["buildability"]] += 1
        categories[row["category"]]["access"][row["credential_access"]] += 1
        if row["status"] != "failed_after_retries":
            auth_counts.update(row["auth"].split("; "))

    matrix_rows = []
    for category, counts in categories.items():
        failed = sum(
            row["status"] == "failed_after_retries"
            for row in results
            if row["category"] == category
        )
        unknown_nonfailed = counts["build"]["unknown"] - failed
        gated = counts["access"]["admin_required"] + counts["access"]["contact_sales"]
        matrix_rows.append(
            f"""
            <tr>
              <th scope="row">{esc(category)}</th>
              <td>{counts["access"]["self_serve"]}</td>
              <td>{gated}</td>
              <td class="good">{counts["build"]["yes"]}</td>
              <td>{counts["build"]["conditional"]}</td>
              <td>{unknown_nonfailed}</td>
              <td class="bad">{failed}</td>
            </tr>"""
        )

    verification_rows = "".join(
        f"""
        <tr>
          <th scope="row">{app["id"]}. {esc(app["app"])}</th>
          <td>{app["first_pass_supported"]}/5</td>
          <td>5/5</td>
          <td><span class="pill {"fixed" if app["result"] == "corrected" else "clean"}">{"Corrected" if app["result"] == "corrected" else "Clean"}</span></td>
          <td><a href="{esc(app["evidence_url"])}" target="_blank" rel="noreferrer">Source</a></td>
        </tr>"""
        for app in verification["apps"]
    )

    failures = [row for row in results if row["status"] == "failed_after_retries"]
    failure_rows = "".join(
        f"""<li><strong>{row["id"]}. {esc(row["app"])}</strong><span>{esc(first_line(row["blocker_or_failure"]))}</span></li>"""
        for row in failures
    )

    verdict_labels = {"yes": "Build now", "conditional": "Conditional", "unknown": "Not proven"}
    table_rows = []
    for row in results:
        evidence = clean(row["evidence_urls"]).split(" | ")[0]
        access = clean(row["credential_access"]).replace("_", " ")
        search_text = " ".join(
            clean(row[key])
            for key in ("app", "category", "auth", "credential_access", "blocker_or_failure")
        ).lower()
        evidence_cell = (
            f'<a href="{esc(evidence)}" target="_blank" rel="noreferrer">Open</a>'
            if evidence
            else '<span class="muted">No source</span>'
        )
        table_rows.append(
            f"""
            <tr data-search="{esc(search_text)}" data-category="{esc(row["category"])}" data-verdict="{esc(row["buildability"])}">
              <td>{row["id"]}</td>
              <th scope="row">{esc(row["app"])}</th>
              <td>{esc(row["category"])}</td>
              <td><span class="pill verdict-{esc(row["buildability"])}">{verdict_labels[row["buildability"]]}</span></td>
              <td>{esc(clean(row["auth"]).replace("; ", ", "))}</td>
              <td>{esc(access)}</td>
              <td>{evidence_cell}</td>
            </tr>"""
        )

    category_options = "".join(
        f'<option value="{esc(category)}">{esc(category)}</option>' for category in categories
    )
    yes_count = sum(row["buildability"] == "yes" for row in results)
    easy_wins = sum(
        row["buildability"] == "yes" and row["credential_access"] in {"self_serve", "not_required"}
        for row in results
    )

    page = TEMPLATE
    replacements = {
        "{{MATRIX_ROWS}}": "".join(matrix_rows),
        "{{VERIFICATION_ROWS}}": verification_rows,
        "{{FAILURE_ROWS}}": failure_rows,
        "{{TABLE_ROWS}}": "".join(table_rows),
        "{{CATEGORY_OPTIONS}}": category_options,
        "{{YES_COUNT}}": str(yes_count),
        "{{EASY_WINS}}": str(easy_wins),
        "{{AUTH_KEY}}": str(auth_counts["api_key"]),
        "{{AUTH_OAUTH}}": str(auth_counts["oauth2"]),
        "{{AUTH_TOKEN}}": str(auth_counts["token"]),
    }
    for marker, value in replacements.items():
        page = page.replace(marker, value)
    OUTPUT_PATH.write_text(page, encoding="utf-8")


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="A two-minute case study of an agent that researched 100 app integrations.">
  <title>100 App Integration Research</title>
  <style>
    :root { color-scheme: light; --bg:#f7f7f5; --paper:#fff; --text:#171715; --muted:#66665f; --line:#deded8; --blue:#3157d5; --green:#177245; --amber:#986400; --red:#b43b32; --radius:12px; --ease-out:cubic-bezier(.23,1,.32,1); }
    * { box-sizing:border-box; }
    html { background:var(--bg); }
    body { margin:0; color:var(--text); background:var(--bg); font:15px/1.5 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    a { color:inherit; text-underline-offset:3px; }
    .page { width:min(1120px,calc(100% - 40px)); margin:auto; }
    header { height:60px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--line); font-size:13px; }
    header strong { font-size:14px; }
    header a { color:var(--muted); }
    .hero { padding:64px 0 36px; }
    .eyebrow { margin:0 0 12px; color:var(--blue); font-weight:700; }
    h1 { max-width:900px; margin:0; font-size:clamp(42px,6.5vw,76px); line-height:.98; letter-spacing:-.055em; }
    .hero > p:last-of-type { max-width:760px; margin:22px 0 0; color:var(--muted); font-size:19px; }
    .scoreboard { display:grid; grid-template-columns:repeat(4,1fr); margin-top:38px; background:var(--line); border:1px solid var(--line); gap:1px; }
    .score { padding:22px; background:var(--paper); }
    .score strong { display:block; font-size:30px; letter-spacing:-.04em; }
    .score span { color:var(--muted); font-size:13px; }
    section { padding:52px 0; border-top:1px solid var(--line); }
    .section-head { display:grid; grid-template-columns:240px 1fr; gap:32px; margin-bottom:28px; }
    .section-head p { margin:0; color:var(--muted); }
    h2 { margin:0; font-size:26px; letter-spacing:-.025em; }
    h3 { margin:0 0 6px; font-size:16px; }
    .answers { display:grid; grid-template-columns:repeat(2,1fr); border:1px solid var(--line); background:var(--line); gap:1px; }
    .answer { min-height:150px; padding:24px; background:var(--paper); }
    .answer .label { display:block; margin-bottom:22px; color:var(--muted); font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; }
    .answer strong { display:block; font-size:24px; line-height:1.2; letter-spacing:-.025em; }
    .answer p { margin:9px 0 0; color:var(--muted); }
    .table-shell { overflow-x:auto; border:1px solid var(--line); background:var(--paper); }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th,td { padding:11px 12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }
    thead th { color:var(--muted); background:#f0f0ec; font-size:11px; text-transform:uppercase; letter-spacing:.045em; }
    tbody tr:last-child > * { border-bottom:0; }
    tbody th { font-weight:650; }
    .matrix td { text-align:center; font-variant-numeric:tabular-nums; }
    .matrix th:first-child { min-width:230px; }
    .good { color:var(--green); font-weight:700; }
    .bad { color:var(--red); font-weight:700; }
    .note { margin:10px 0 0; color:var(--muted); font-size:12px; }
    .workflow { display:grid; grid-template-columns:repeat(4,1fr); border:1px solid var(--line); background:var(--line); gap:1px; counter-reset:step; }
    .step { padding:22px; background:var(--paper); counter-increment:step; }
    .step::before { content:"0" counter(step); display:block; margin-bottom:28px; color:var(--blue); font:700 12px/1 ui-monospace,SFMono-Regular,monospace; }
    .step p { margin:8px 0 0; color:var(--muted); font-size:13px; }
    .human { border-top:3px solid var(--amber); }
    .proof-grid { display:grid; grid-template-columns:.8fr 1.2fr; gap:18px; }
    .card { padding:24px; border:1px solid var(--line); background:var(--paper); border-radius:var(--radius); }
    .card p { color:var(--muted); }
    pre { overflow:auto; margin:18px 0; padding:16px; background:#171715; color:#f7f7f5; border-radius:8px; font:12px/1.6 ui-monospace,SFMono-Regular,monospace; }
    .button { display:inline-flex; min-height:42px; align-items:center; padding:0 15px; border-radius:8px; background:var(--blue); color:#fff; text-decoration:none; font-weight:700; transition:transform 140ms var(--ease-out); }
    .button:active { transform:scale(.97); }
    .accuracy { display:flex; align-items:center; gap:18px; margin:18px 0 22px; }
    .accuracy strong { font-size:34px; letter-spacing:-.04em; }
    .arrow { color:var(--muted); }
    .pill { display:inline-flex; white-space:nowrap; padding:3px 7px; border-radius:999px; font-size:11px; font-weight:700; background:#ecece7; }
    .clean,.verdict-yes { color:var(--green); background:#e5f3eb; }
    .fixed,.verdict-conditional { color:var(--amber); background:#f7efd9; }
    .verdict-unknown { color:var(--muted); }
    .failures { columns:2; padding:0; margin:0; list-style:none; }
    .failures li { break-inside:avoid; display:grid; gap:4px; padding:13px 0; border-bottom:1px solid var(--line); }
    .failures span { color:var(--muted); font-size:12px; }
    .controls { display:grid; grid-template-columns:1fr 240px 170px; gap:9px; margin-bottom:14px; }
    input,select { min-height:42px; width:100%; padding:0 11px; border:1px solid var(--line); border-radius:8px; background:var(--paper); color:var(--text); font:inherit; }
    .results-meta { margin:0 0 12px; color:var(--muted); font-size:13px; }
    .apps-table { min-width:900px; }
    .apps-table td:first-child { width:44px; color:var(--muted); font-variant-numeric:tabular-nums; }
    .apps-table th:nth-child(2) { min-width:160px; }
    .muted { color:var(--muted); }
    footer { padding:32px 0 60px; color:var(--muted); font-size:12px; border-top:1px solid var(--line); }
    [hidden] { display:none!important; }
    @media (max-width:780px) { .page { width:min(100% - 24px,1120px); } .hero { padding-top:44px; } .scoreboard,.answers { grid-template-columns:1fr 1fr; } .section-head,.proof-grid { grid-template-columns:1fr; gap:14px; } .workflow { grid-template-columns:1fr 1fr; } .controls { grid-template-columns:1fr; } .failures { columns:1; } }
    @media (max-width:480px) { .scoreboard,.answers,.workflow { grid-template-columns:1fr; } h1 { font-size:43px; } }
    @media (prefers-reduced-motion:reduce) { .button { transition:none; } }
  </style>
</head>
<body>
  <div class="page">
    <header><strong>100 App Integration Research</strong><a href="https://github.com/Anushlinux/research-assignment/tree/codex/milestone-1-1-hardening">Source repository</a></header>
    <main>
      <div class="hero">
        <p class="eyebrow">The two-minute answer</p>
        <h1>APIs are common. Getting production access is the real blocker.</h1>
        <p>An agent attempted all 100 apps. It found many callable surfaces, but documentation often failed to prove who can create credentials, which plan is required, or whether production approval is needed.</p>
        <div class="scoreboard" aria-label="Headline results">
          <div class="score"><strong>100</strong><span>apps attempted</span></div>
          <div class="score"><strong>92</strong><span>completed records</span></div>
          <div class="score"><strong>{{YES_COUNT}}</strong><span>buildable now</span></div>
          <div class="score"><strong>8</strong><span>unresolved after retries</span></div>
        </div>
      </div>
      <section id="findings">
        <div class="section-head"><h2>What the research says</h2><p>Four conclusions a reviewer should remember.</p></div>
        <div class="answers">
          <article class="answer"><span class="label">Dominant auth</span><strong>API key {{AUTH_KEY}} · OAuth 2.0 {{AUTH_OAUTH}} · Token {{AUTH_TOKEN}}</strong><p>Apps can support more than one method, so these counts overlap.</p></article>
          <article class="answer"><span class="label">Best starting point</span><strong>Productivity is the clearest entry point.</strong><p>Six of ten apps are directly buildable; eight have confirmed self-serve access.</p></article>
          <article class="answer"><span class="label">Most common blocker</span><strong>47 credential paths remain unproven.</strong><p>The API may exist, but the docs do not establish a usable production-access path.</p></article>
          <article class="answer"><span class="label">Recommended action</span><strong>Start with {{EASY_WINS}} easy wins. Use outreach for gated apps.</strong><p>Do not mistake missing evidence for “no API.” Keep it unknown until sales, admin, or partner access confirms it.</p></article>
        </div>
      </section>
      <section>
        <div class="section-head"><h2>Category matrix</h2><p>Self-serve and gated describe credential access. The final four columns describe buildability and always total ten apps.</p></div>
        <div class="table-shell"><table class="matrix"><thead><tr><th>Category</th><th>Self-serve</th><th>Gated</th><th>Build now</th><th>Conditional</th><th>Needs proof</th><th>Failed run</th></tr></thead><tbody>{{MATRIX_ROWS}}</tbody></table></div>
        <p class="note">Gated means confirmed administrator or sales involvement. “Needs proof” is an evidence gap, not a negative finding.</p>
      </section>
      <section id="agent">
        <div class="section-head"><h2>What I built</h2><p>A bounded agent where models interpret evidence, but code decides what may enter the final result.</p></div>
        <div class="workflow">
          <article class="step"><h3>Find evidence</h3><p>Composio Search runs role-specific queries and keeps official sources.</p></article>
          <article class="step"><h3>Extract claims</h3><p>OpenAI turns stored excerpts into a structured app record.</p></article>
          <article class="step"><h3>Verify and admit</h3><p>A second pass checks each claim. Deterministic rules remove unsupported claims and compute buildability.</p></article>
          <article class="step human"><h3>Human needed here</h3><p>Review a sample, inspect ambiguous sources, and contact sales or administrators where public evidence stops.</p></article>
        </div>
      </section>
      <section id="proof">
        <div class="section-head"><h2>Proof and verification</h2><p>The application is runnable, and the first pass visibly improved after verification.</p></div>
        <div class="proof-grid">
          <article class="card"><h3>Run the agent</h3><p>Every attempt preserves search, source, snippet, draft, audit, diff, validation, and final artifacts.</p><pre><code>uv sync --frozen

uv run --frozen research run \\
  --app-id 61 \\
  --run-id github-check</code></pre><a class="button" href="https://github.com/Anushlinux/research-assignment/tree/codex/milestone-1-1-hardening">Open source and README</a></article>
          <article class="card"><h3>12-app accuracy sample</h3><div class="accuracy"><strong>52/60</strong><span class="arrow">→</span><strong>60/60</strong></div><p>Five material claims were checked for each sampled app. Six apps were clean; six needed at least one correction. This measures agreement with the stored official evidence, not a claimed global accuracy score.</p><div class="table-shell"><table><thead><tr><th>App</th><th>First pass</th><th>Final</th><th>Result</th><th>Evidence</th></tr></thead><tbody>{{VERIFICATION_ROWS}}</tbody></table></div></article>
        </div>
      </section>
      <section><div class="section-head"><h2>What failed honestly</h2><p>Eight apps stayed unresolved. They remain visible instead of being silently dropped.</p></div><ul class="failures">{{FAILURE_ROWS}}</ul></section>
      <section id="results">
        <div class="section-head"><h2>All 100 apps</h2><p>Server-rendered in catalog order. Salesforce is row 1 even when JavaScript is disabled.</p></div>
        <div class="controls"><input id="search" type="search" aria-label="Search apps" placeholder="Search app, auth, category, or blocker"><select id="category" aria-label="Filter category"><option value="">All categories</option>{{CATEGORY_OPTIONS}}</select><select id="verdict" aria-label="Filter verdict"><option value="">All verdicts</option><option value="yes">Build now</option><option value="conditional">Conditional</option><option value="unknown">Not proven</option></select></div>
        <p class="results-meta"><strong id="result-count">100</strong> apps shown</p>
        <div class="table-shell"><table class="apps-table"><thead><tr><th>#</th><th>App</th><th>Category</th><th>Verdict</th><th>Auth</th><th>Access</th><th>Evidence</th></tr></thead><tbody id="app-rows">{{TABLE_ROWS}}</tbody></table></div>
      </section>
    </main>
    <footer>Evidence-backed integration research · 100 attempted · 92 completed · 8 unresolved · August 2026</footer>
  </div>
  <script>
    const search = document.querySelector('#search');
    const category = document.querySelector('#category');
    const verdict = document.querySelector('#verdict');
    const rows = [...document.querySelectorAll('#app-rows tr')];
    const count = document.querySelector('#result-count');
    function filterRows() {
      const query = search.value.trim().toLowerCase();
      let visible = 0;
      for (const row of rows) {
        const show = (!query || row.dataset.search.includes(query)) && (!category.value || row.dataset.category === category.value) && (!verdict.value || row.dataset.verdict === verdict.value);
        row.hidden = !show;
        if (show) visible += 1;
      }
      count.textContent = visible;
    }
    for (const control of [search, category, verdict]) control.addEventListener('input', filterRows);
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    build()
