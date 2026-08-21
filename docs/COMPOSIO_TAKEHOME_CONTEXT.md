# Composio Product Internship Take-Home: Full Research Agent Context

## Purpose of this file

This file is the complete implementation brief for Codex.

It contains:

- The assignment and what the reviewer is actually evaluating.
- The complete list of 100 apps.
- The architecture selected for the research system.
- The exact role of Composio, OpenAI, MCP, browser automation, deterministic code, and human verification.
- The output schema and evidence requirements.
- The repository structure, commands, tests, milestones, and time limits.
- The implementation rules Codex must follow.

The current phase is **Phase 1: build the research pipeline and produce trustworthy structured output**.

Do not build the final HTML case study yet. The findings, pattern analysis, visual presentation, and final verification report will be built after the research output exists.

---

## 1. Original assignment, normalized

Composio turns applications into tools that AI agents can call. Before Composio builds a toolkit for an app, it needs to research:

- What the app does.
- What authentication methods its developer interfaces use.
- Whether credentials are self-serve or gated.
- Whether the app has a documented public API.
- How broad that API is.
- Whether the app already has an MCP server.
- Whether it can be turned into an agent-callable toolkit today.
- What blocks integration when it cannot.
- Which official pages support every answer.

The assignment provides 100 apps across 10 categories.

For each app, the final research record must capture at least:

1. Category.
2. A one-line description.
3. Authentication method or methods.
4. Self-serve versus gated developer access.
5. Public API availability and protocol.
6. Approximate API breadth.
7. Existing official or community MCP.
8. Buildability verdict.
9. Main blocker, when applicable.
10. Evidence URLs behind the claims.

The assignment then asks for three higher-level outputs:

### A. Patterns

The submission cannot be only 100 rows. It must later identify patterns such as:

- Which authentication methods dominate.
- Which categories are most self-serve.
- Which categories are most gated.
- Common blockers.
- Easy integration wins.
- Apps requiring partnership, sales, approval, or customer-owned credentials.

### B. An agent or automated pipeline

The research must be performed by an agent, script, or pipeline rather than manually entering all 100 rows.

Using Composio's SDK and MCP is strongly aligned with the role.

The final submission must explain:

- What the system did.
- What was deterministic.
- What the model decided.
- Where browser automation was needed.
- Where a human was needed.
- Which failures remained.

### C. Verification

Accuracy is the main priority.

The final submission must later show:

- A sample manually cross-checked against real documentation.
- What the first pass got right and wrong.
- What automated verification changed.
- How final accuracy improved.
- Honest unresolved cases.

The final deliverable will eventually be one self-explanatory HTML page or case study that a reviewer can understand in about two minutes, plus a source repository and runnable instructions.

That is not the current phase.

---

## 2. What the reviewer is actually testing

The visible task is to research 100 apps. The deeper test is whether the candidate can design a reliable product operations system.

The reviewer is likely testing these capabilities:

1. **Source discovery**
   - Can the system repeatedly find the right official developer pages?

2. **Entity resolution**
   - Can it avoid confusing products with similar names such as Plain, Close, Grain, Fathom, Consensus, Twenty, and Front?

3. **Claim extraction**
   - Can it separate authentication, developer signup, production approval, pricing gates, API scope, and MCP availability?

4. **Evidence discipline**
   - Can every important conclusion be traced to a fetched source?

5. **Uncertainty handling**
   - Can it say `unknown` rather than invent an answer?

6. **Negative-claim discipline**
   - Can it avoid claiming that an API or MCP does not exist merely because search failed?

7. **Operational scale**
   - Can it run across 100 heterogeneous apps with caching, retries, concurrency, and resumability?

8. **Verification design**
   - Can it measure and improve quality instead of treating one model response as truth?

9. **Presentation judgment**
   - Can it later compress the work into a clear two-minute case study?

The system must therefore optimize for **traceability and recoverability**, not only for raw speed.

---

## 3. Main architecture decision

Build a **bounded research pipeline with an agent fallback**.

Do not create 100 fully autonomous browsing agents.

The core flow is:

```text
data/apps.csv
    |
    v
async Python coordinator
    |
    v
Composio Search
    |-- focused web searches
    |-- official source selection
    `-- official page content fetches
    |
    v
OpenAI structured extraction
    |
    v
deterministic validation and verdict rules
    |
    |-- supported and internally consistent -> final record
    |
    `-- missing, conflicting, negative, or low-confidence claim
             |
             v
       verifier agent
       using Composio MCP
             |
             |-- Composio Search
             `-- Composio Browser Tool when needed
             |
             v
       corrected record plus diff
```

The key design rule is:

> Search and page retrieval happen through Composio. OpenAI is used for inference over retrieved content, not as the web-search provider.

Do not attach OpenAI's built-in `WebSearchTool` to either the extraction path or verifier.

---

## 4. Why this architecture was selected

### Why not one free-roaming agent per app

A free-roaming agent for every app would be easy to describe but difficult to trust.

It would create:

- Unbounded tool calls.
- Inconsistent search strategies.
- Repeated fetches.
- Higher latency.
- Higher cost.
- Harder retries.
- Harder debugging.
- Poor evidence traceability.
- Results that are difficult to compare across apps.

### Why a deterministic coordinator is better

A normal Python coordinator controls:

- Which queries run.
- Which URLs are selected.
- How many sources are fetched.
- What is cached.
- How each claim is validated.
- Which records need escalation.
- How the run resumes after failure.
- How draft and corrected results are compared.

### Why an agent still matters

An agent is useful only for the part where flexible judgment is genuinely needed:

- Resolving conflicting documentation.
- Navigating pages that are difficult to fetch.
- Investigating ambiguous product identity.
- Independently checking disputed fields.
- Recovering from unusual documentation structures.

This gives the assignment a real agentic component without letting autonomous behavior control the entire 100-app run.

### Why direct Composio SDK calls are the default

Direct session execution gives the application a controlled code path and makes logging, retries, budgets, and output storage simple.

### Why Composio MCP is used only for verification

The verifier agent benefits from being able to decide which search or browser action to call.

MCP is appropriate for this bounded fallback. It should not be the only path because direct execution is easier to inspect, gate, and reproduce.

---

## 5. Exact technology choices

### Runtime

- Python 3.12.
- `uv` for environment and dependency management.
- `asyncio` for app-level concurrency.
- `Typer` for the command-line interface.
- JSON and JSONL for run artifacts.
- No database in Phase 1.

### Main packages

```text
composio
openai
openai-agents
pydantic
pydantic-settings
tenacity
typer
rich
```

Development packages:

```text
pytest
pytest-asyncio
ruff
mypy
```

### Component responsibilities

| Component | Responsibility |
|---|---|
| Codex | Builds, tests, runs, and debugs the repository |
| Composio CLI | Local setup, schema inspection, tool smoke tests, and debugging |
| Composio Python SDK | Creates the restricted session and executes search/fetch/browser tools |
| Composio Search | Discovers official pages and fetches page content |
| Composio Browser Tool | Fallback for JavaScript-heavy, blocked, interactive, or navigation-dependent pages |
| Composio MCP | Exposes only the approved research tools to the verifier agent |
| OpenAI Responses API | Produces structured records from fetched source content |
| OpenAI Agents SDK | Runs the verifier agent with the restricted Composio MCP endpoint |
| Pydantic | Defines strict records and enums |
| Deterministic Python | Source ranking, validation, verdict rules, confidence, caching, retry, and persistence |

### Model policy

Use environment variables rather than scattering model IDs through the code.

Recommended defaults:

```text
OPENAI_MODEL_EXTRACT=gpt-5.6-luna
OPENAI_MODEL_VERIFY=gpt-5.6-terra
```

The extraction workload is repetitive and high-volume, so the lower-cost model is appropriate for the first pass.

The verifier handles fewer, harder cases, so it can use the stronger model.

The system must still work when these environment variables are changed.

---

## 6. Composio tool policy

Only these Composio tools are required in Phase 1:

### Composio Search

- `COMPOSIO_SEARCH_WEB`
- `COMPOSIO_SEARCH_FETCH_URL_CONTENT`

### Composio Browser Tool

- `BROWSER_TOOL_CREATE_TASK`
- `BROWSER_TOOL_WATCH_TASK`
- `BROWSER_TOOL_GET_SESSION`
- `BROWSER_TOOL_GET_OUTPUT_FILE`
- `BROWSER_TOOL_STOP_TASK`, optional for cleanup

Codex must **not guess the request schemas** for these tools.

Before implementing wrappers, Codex must inspect each schema through the Composio CLI:

```bash
composio execute COMPOSIO_SEARCH_WEB --get-schema
composio execute COMPOSIO_SEARCH_FETCH_URL_CONTENT --get-schema
composio execute BROWSER_TOOL_CREATE_TASK --get-schema
composio execute BROWSER_TOOL_WATCH_TASK --get-schema
composio execute BROWSER_TOOL_GET_SESSION --get-schema
composio execute BROWSER_TOOL_GET_OUTPUT_FILE --get-schema
```

Save the inspected schemas or summarized parameter notes under:

```text
docs/composio-tool-schemas/
```

The CLI is a development and debugging aid. The submitted pipeline runtime must use the Composio Python SDK, not shell out to the CLI for every app.

---

## 7. Restricted Composio session

The application should create one fixed session for this research job and reuse it.

Approximate setup:

```python
from composio import Composio, SESSION_PRESET_DIRECT_TOOLS

composio = Composio()

session = composio.sessions.create(
    user_id="composio-takehome-research",
    toolkits=["composio_search", "browser_tool"],
    tools={
        "composio_search": {
            "enable": [
                "COMPOSIO_SEARCH_WEB",
                "COMPOSIO_SEARCH_FETCH_URL_CONTENT",
            ]
        },
        "browser_tool": {
            "enable": [
                "BROWSER_TOOL_CREATE_TASK",
                "BROWSER_TOOL_WATCH_TASK",
                "BROWSER_TOOL_GET_SESSION",
                "BROWSER_TOOL_GET_OUTPUT_FILE",
                "BROWSER_TOOL_STOP_TASK",
            ]
        },
    },
    session_preset=SESSION_PRESET_DIRECT_TOOLS,
    mcp=True,
)
```

The exact imports and method signatures must be confirmed against the installed SDK.

Persist the returned session ID locally, for example:

```text
.state/composio_session.json
```

On later runs, reuse the session:

```python
session = composio.use(session_id, mcp=True)
```

Do not create a new session for every app.

### Direct path

The coordinator executes known tools through the session:

```python
result = session.execute(
    "COMPOSIO_SEARCH_WEB",
    arguments=validated_arguments,
)
```

### MCP path

The same restricted session exposes:

```python
session.mcp.url
session.mcp.headers
```

The verifier agent receives a `HostedMCPTool` configured with this endpoint.

Because the session uses the direct-tools preset, the MCP endpoint should expose only the listed research tools rather than a broad tool surface.

---

## 8. OpenAI usage policy

OpenAI is used for two jobs only.

### A. Structured extraction

Input:

- One app identity.
- The field definitions.
- The selected fetched official pages.
- Source identifiers assigned by the pipeline.
- Strict instructions to use only supplied sources.

Output:

- One Pydantic `AppResearch` object.

Use the Responses API structured output path:

```python
response = client.responses.parse(
    model=settings.openai_model_extract,
    input=[
        {"role": "system", "content": extraction_instructions},
        {"role": "user", "content": app_and_sources},
    ],
    text_format=AppResearch,
)

record = response.output_parsed
```

Codex must confirm the exact installed SDK signature before finalizing this wrapper.

### B. Verifier agent

The verifier receives:

- The app identity.
- The first-pass record.
- Only the fields that failed validation.
- Instructions to independently verify those fields.
- The restricted Composio MCP tools.

It must return a structured correction object, not a prose essay.

### Explicit prohibition

Do not use:

- OpenAI web search.
- OpenAI browser tools.
- Model prior knowledge as evidence.
- A prompt asking the model to research an app without supplied sources.

The model may interpret sources. It may not invent facts outside those sources.

---

## 9. Input data contract

Create:

```text
data/apps.csv
```

Columns:

```text
id
app_name
website_hint
category
notes
```

The supplied website is an identity and source hint, not always a complete canonical domain.

Some apps have documentation on a different official domain. Examples include:

- LinkedIn documentation on Microsoft Learn.
- Meta products on Facebook developer domains.
- Open-source projects on GitHub.
- Enterprise products with separate documentation domains.

The pipeline must allow an official documentation domain that is:

1. Directly supplied in the assignment, or
2. Linked from an already trusted official page, or
3. Clearly an official vendor-owned documentation property and recorded with identity evidence.

Ambiguous apps must be flagged rather than silently resolved.

---

## 10. Complete 100-app input

The following block can be copied directly into `data/apps.csv`.

```csv
id,app_name,website_hint,category,notes
1,Salesforce,salesforce.com,CRM and Sales,
2,HubSpot,hubspot.com,CRM and Sales,
3,Pipedrive,pipedrive.com,CRM and Sales,
4,Attio,attio.com,CRM and Sales,
5,Twenty,twenty.com,CRM and Sales,Open-source CRM
6,Podio,podio.com,CRM and Sales,
7,Zoho CRM,zoho.com/crm,CRM and Sales,
8,Close,close.com,CRM and Sales,
9,Copper,copper.com,CRM and Sales,
10,DealCloud,api.docs.dealcloud.com,CRM and Sales,
11,Zendesk,zendesk.com,Support and Helpdesk,
12,Intercom,intercom.com,Support and Helpdesk,
13,Freshdesk,freshdesk.com,Support and Helpdesk,
14,Front,front.com,Support and Helpdesk,
15,Pylon,usepylon.com,Support and Helpdesk,
16,LiveAgent,liveagent.com,Support and Helpdesk,
17,Plain,plain.com,Support and Helpdesk,
18,Help Scout,helpscout.com,Support and Helpdesk,
19,Gorgias,gorgias.com,Support and Helpdesk,
20,Gladly,gladly.com,Support and Helpdesk,
21,Slack,slack.com,Communications and Messaging,
22,Twilio,twilio.com,Communications and Messaging,
23,Zoho Cliq,zoho.com/cliq,Communications and Messaging,
24,Lark (Larksuite),open.larksuite.com,Communications and Messaging,
25,Pumble,pumble.com,Communications and Messaging,
26,Discord,discord.com,Communications and Messaging,
27,Telegram,core.telegram.org,Communications and Messaging,
28,WhatsApp Business,developers.facebook.com/docs/whatsapp,Communications and Messaging,
29,Aircall,aircall.io,Communications and Messaging,
30,Vonage,developer.vonage.com,Communications and Messaging,
31,Google Ads,developers.google.com/google-ads,"Marketing, Ads, Email and Social",
32,Meta Ads,developers.facebook.com/docs/marketing-apis,"Marketing, Ads, Email and Social",
33,LinkedIn Ads,learn.microsoft.com/linkedin/marketing,"Marketing, Ads, Email and Social",
34,GoHighLevel,highlevel.stoplight.io,"Marketing, Ads, Email and Social",
35,Mailchimp,mailchimp.com/developer,"Marketing, Ads, Email and Social",
36,Klaviyo,developers.klaviyo.com,"Marketing, Ads, Email and Social",
37,systeme.io,systeme.io,"Marketing, Ads, Email and Social",Funnel builder
38,Pinterest,developers.pinterest.com,"Marketing, Ads, Email and Social",
39,Threads (Meta),developers.facebook.com/docs/threads,"Marketing, Ads, Email and Social",
40,SendGrid,sendgrid.com,"Marketing, Ads, Email and Social",
41,Shopify,shopify.dev,Ecommerce,
42,WooCommerce,woocommerce.com/document/woocommerce-rest-api,Ecommerce,
43,BigCommerce,developer.bigcommerce.com,Ecommerce,
44,Salesforce Commerce Cloud,developer.salesforce.com/docs/commerce,Ecommerce,
45,Magento (Adobe Commerce),developer.adobe.com/commerce,Ecommerce,
46,Squarespace,developers.squarespace.com,Ecommerce,
47,Ecwid,api-docs.ecwid.com,Ecommerce,
48,Gumroad,gumroad.com/api,Ecommerce,
49,Amazon Selling Partner,developer-docs.amazon.com/sp-api,Ecommerce,
50,fanbasis,fanbasis.com,Ecommerce,
51,DataForSEO,docs.dataforseo.com,"Data, SEO and Scraping",
52,SE Ranking,seranking.com/api,"Data, SEO and Scraping",
53,Ahrefs,ahrefs.com/api,"Data, SEO and Scraping",
54,MrScraper,docs.mrscraper.com,"Data, SEO and Scraping",
55,Apify,docs.apify.com,"Data, SEO and Scraping",
56,Firecrawl,firecrawl.dev,"Data, SEO and Scraping",
57,Bright Data,brightdata.com,"Data, SEO and Scraping",
58,Sherlock,github.com/sherlock-project/sherlock,"Data, SEO and Scraping",Open-source username search tool
59,Waterfall.io,waterfall.io,"Data, SEO and Scraping",Contact and company intelligence
60,Clay,clay.com,"Data, SEO and Scraping",
61,GitHub,docs.github.com/rest,"Developer, Infra and Data platforms",
62,Vercel,vercel.com/docs/rest-api,"Developer, Infra and Data platforms",
63,Netlify,docs.netlify.com/api,"Developer, Infra and Data platforms",
64,Cloudflare,developers.cloudflare.com/api,"Developer, Infra and Data platforms",
65,Supabase,supabase.com/docs,"Developer, Infra and Data platforms",
66,Neo4j,neo4j.com/docs/api,"Developer, Infra and Data platforms",
67,Snowflake,docs.snowflake.com,"Developer, Infra and Data platforms",
68,MongoDB Atlas,mongodb.com/docs/atlas/api,"Developer, Infra and Data platforms",
69,Datadog,docs.datadoghq.com/api,"Developer, Infra and Data platforms",
70,Sentry,docs.sentry.io/api,"Developer, Infra and Data platforms",
71,Notion,developers.notion.com,Productivity and Project Management,
72,Airtable,airtable.com/developers,Productivity and Project Management,
73,Linear,developers.linear.app,Productivity and Project Management,
74,Jira,developer.atlassian.com,Productivity and Project Management,
75,Asana,developers.asana.com,Productivity and Project Management,
76,Monday.com,developer.monday.com,Productivity and Project Management,
77,ClickUp,clickup.com/api,Productivity and Project Management,
78,Coda,coda.io/developers,Productivity and Project Management,
79,Smartsheet,smartsheet.com/developers,Productivity and Project Management,
80,Harvest,help.getharvest.com/api-v2,Productivity and Project Management,Main site: harvestapp.com
81,Stripe,stripe.com/docs/api,Finance and Fintech,
82,Plaid,plaid.com/docs,Finance and Fintech,
83,Binance,binance-docs.github.io,Finance and Fintech,
84,Paygent Connect,,Finance and Fintech,"Paygent, NMI-powered; identity must be resolved carefully"
85,iPayX,ipayx.ai/docs,Finance and Fintech,
86,QuickBooks,developer.intuit.com,Finance and Fintech,
87,Xero,developer.xero.com,Finance and Fintech,
88,Brex,developer.brex.com,Finance and Fintech,
89,Ramp,docs.ramp.com,Finance and Fintech,
90,PitchBook,pitchbook.com,Finance and Fintech,Research API
91,NotebookLM,cloud.google.com/gemini,"AI, Research and Media-native",Enterprise API hint
92,Otter AI,help.otter.ai,"AI, Research and Media-native",MCP server hint
93,Fathom,fathom.video,"AI, Research and Media-native",
94,Consensus,consensus.app,"AI, Research and Media-native",OAuth requested
95,Reducto,reducto.ai,"AI, Research and Media-native",Document parsing
96,Devin,docs.devin.ai,"AI, Research and Media-native",MCP hint
97,higgsfield,higgsfield.ai/cli,"AI, Research and Media-native",Content suite
98,Mermaid CLI,github.com/mermaid-js/mermaid-cli,"AI, Research and Media-native",
99,YouTube Transcript,transcriptapi.com,"AI, Research and Media-native",
100,Grain,grain.com,"AI, Research and Media-native",Meeting notes
```

---

## 11. Output philosophy

The first useful output is not the HTML page.

The first useful output is:

```text
runs/<run_id>/final/results.json
```

Every row must be machine-readable, internally consistent, and evidence-backed.

The output must support three later consumers:

1. The final table on the HTML page.
2. Pattern analysis across all 100 apps.
3. Accuracy measurement against a manually verified sample.

Store raw inputs, drafts, corrections, and final records separately. Never overwrite the first-pass result.

---

## 12. Proposed Pydantic schema

The exact implementation may be adjusted during the five-app pilot, but Codex must preserve the distinctions below.

```python
from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field, HttpUrl


class AuthMethod(StrEnum):
    OAUTH2 = "oauth2"
    OAUTH1 = "oauth1"
    API_KEY = "api_key"
    BASIC = "basic"
    BEARER_TOKEN = "bearer_token"
    PERSONAL_ACCESS_TOKEN = "personal_access_token"
    SERVICE_ACCOUNT = "service_account"
    JWT = "jwt"
    SIGNED_REQUEST = "signed_request"
    SESSION_COOKIE = "session_cookie"
    NONE = "none"
    OTHER = "other"
    UNKNOWN = "unknown"


class DeveloperAccess(StrEnum):
    SELF_SERVE_FREE = "self_serve_free"
    SELF_SERVE_TRIAL = "self_serve_trial"
    SELF_SERVE_PAID = "self_serve_paid"
    ADMIN_REQUIRED = "admin_required"
    VENDOR_REVIEW = "vendor_review"
    PARTNER_ONLY = "partner_only"
    CONTACT_SALES = "contact_sales"
    NOT_AVAILABLE = "not_available"
    UNKNOWN = "unknown"


class ProductionGate(StrEnum):
    NONE = "none"
    PAID_PLAN = "paid_plan"
    APP_REVIEW = "app_review"
    ADMIN_APPROVAL = "admin_approval"
    VENDOR_APPROVAL = "vendor_approval"
    PARTNER_APPROVAL = "partner_approval"
    CONTACT_SALES = "contact_sales"
    CUSTOMER_ACCOUNT_REQUIRED = "customer_account_required"
    UNKNOWN = "unknown"


class ApiAvailability(StrEnum):
    YES = "yes"
    LIMITED = "limited"
    NO = "no"
    UNKNOWN = "unknown"


class ApiProtocol(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"
    SOAP = "soap"
    RPC = "rpc"
    WEBSOCKET = "websocket"
    WEBHOOK = "webhook"
    CLI = "cli"
    SDK_ONLY = "sdk_only"
    OTHER = "other"
    UNKNOWN = "unknown"


class ApiBreadth(StrEnum):
    BROAD = "broad"
    MODERATE = "moderate"
    NARROW = "narrow"
    NONE = "none"
    UNKNOWN = "unknown"


class Ternary(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class McpStatus(StrEnum):
    OFFICIAL = "official"
    COMMUNITY = "community"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


class Buildability(StrEnum):
    YES = "yes"
    CONDITIONAL = "conditional"
    NO = "no"
    UNKNOWN = "unknown"


class SourceTier(StrEnum):
    OFFICIAL_DEVELOPER_DOCS = "official_developer_docs"
    OFFICIAL_HELP = "official_help"
    OFFICIAL_PRICING = "official_pricing"
    OFFICIAL_GITHUB = "official_github"
    OFFICIAL_BLOG = "official_blog"
    OFFICIAL_WEBSITE = "official_website"
    THIRD_PARTY = "third_party"


class Evidence(BaseModel):
    source_id: str
    url: HttpUrl
    title: str
    source_tier: SourceTier
    excerpt: str = Field(max_length=500)
    supports: list[str]
    fetch_method: str
    retrieved_at: datetime
    content_hash: str | None = None
    raw_path: str | None = None


class ApiCapabilities(BaseModel):
    read: Ternary
    write: Ternary
    webhooks_or_events: Ternary


class AppResearch(BaseModel):
    app_id: int
    app_name: str
    website_hint: str
    category: str

    identity_status: str
    canonical_product_name: str
    official_domains: list[str]

    one_line_description: str

    auth_methods: list[AuthMethod]
    auth_notes: str

    developer_access: DeveloperAccess
    production_gates: list[ProductionGate]
    access_notes: str

    api_availability: ApiAvailability
    api_protocols: list[ApiProtocol]
    api_breadth: ApiBreadth
    api_capabilities: ApiCapabilities
    api_surface_summary: str

    mcp_status: McpStatus
    mcp_url: HttpUrl | None
    mcp_notes: str

    buildability: Buildability
    integration_paths: list[str]
    main_blocker: str | None

    unresolved_questions: list[str]
    evidence: list[Evidence]

    needs_human_review: bool
    generated_at: datetime
    model: str
    pipeline_version: str
```

### Schema design reasons

#### Authentication is a list

An app can support multiple paths at once, for example:

- OAuth2 for marketplace integrations.
- API keys for private integrations.
- Basic authentication for legacy endpoints.
- Service accounts for enterprise access.

A single auth field would lose information.

#### Self-serve and production gating are separate

An app may let anyone:

- Create a developer account.
- Create a test app.
- Obtain sandbox credentials.

But production use may still require:

- Paid plan.
- Admin approval.
- App review.
- Partner approval.
- Contact sales.

A binary self-serve field would hide this distinction.

#### MCP absence is not treated as proven non-existence

`not_found` means:

> No relevant MCP was found in the searches and official repositories checked by this run.

It does not mean:

> No MCP exists anywhere.

#### Buildability is not a free-form model opinion

The model extracts facts. Deterministic code calculates the main verdict using defined rules.

---

## 13. Required field definitions

Codex must put these definitions in the extraction prompt and tests.

### API breadth

#### Broad

Use when the API covers most important product resources, supports meaningful read and write operations, and usually includes webhooks, events, or an equivalent change mechanism.

#### Moderate

Use when the API exposes several useful resources but has meaningful limitations, partial write support, or incomplete product coverage.

#### Narrow

Use when the interface exposes one specialized workflow, only a few endpoints, a highly constrained export, or a limited read-only surface.

#### None

Use only when explicit evidence establishes that there is no supported developer interface relevant to the product.

#### Unknown

Use when available sources do not establish breadth confidently.

### Developer access

#### Self-serve free

A developer can independently create credentials on a free account.

#### Self-serve trial

A developer can independently create credentials during a trial.

#### Self-serve paid

Credentials are available without vendor approval, but only after purchasing a plan.

#### Admin required

A developer can use the interface only when an administrator of a customer workspace enables or creates credentials.

#### Vendor review

A developer account or app can be created, but meaningful use requires review by the vendor.

#### Partner only

The interface is available only through a formal partner program.

#### Contact sales

Documentation or access requires sales involvement, enterprise contracting, or a non-public process.

#### Unknown

The source set does not establish the access path.

### Buildability

#### Yes

Use when:

- A documented public API, GraphQL interface, official MCP, or usable local CLI exists.
- It exposes meaningful agent-callable actions.
- A realistic credential or local execution path exists today.

#### Conditional

Use when:

- The integration surface exists, but requires a paid plan, customer admin, app review, partnership, or customer-owned credentials.
- The API is narrow or read-only.
- Production access is materially more difficult than sandbox access.
- A community MCP exists but official support is absent.
- An agent toolkit is possible for existing customers but not generally self-serve.

#### No

Use only when:

- Official evidence establishes no supported usable interface.
- Access is effectively unavailable outside a private partnership.
- The available interface exposes no useful agent-callable operation.
- Legal or platform restrictions make the intended toolkit impractical.

#### Unknown

Use when the evidence is insufficient or conflicting.

---

## 14. Source and evidence rules

### Source priority

Use this ranking:

1. Official developer documentation.
2. Official authentication or integration documentation.
3. Official support documentation.
4. Official pricing or plan documentation.
5. Official GitHub organization or repository.
6. Official product blog.
7. Official marketing page.
8. Third-party source only when unavoidable.

### Search-result snippets are not final evidence

Search snippets can identify candidate pages.

A claim is supported only after the selected page itself is fetched or inspected through the browser tool.

### Evidence must map to fields

Each `Evidence.supports` list should contain field paths such as:

```text
auth_methods
developer_access
production_gates
api_availability
api_protocols
api_breadth
mcp_status
buildability
```

Validation should ensure every required non-unknown field has at least one source that claims to support it.

### Excerpts

Store a short excerpt, normally one or two sentences, sufficient for later human review.

Do not store large copied pages inside `results.json`.

Store complete fetched content separately under the run directory.

### Negative claim rule

Never infer `api_availability=no` from:

- No search result.
- A failed fetch.
- A marketing page without an API link.
- The model's prior knowledge.

Use `no` only when an authoritative source explicitly supports the absence or deprecation.

Otherwise use `unknown`.

The same rule applies to MCP. Use `not_found`, not a definitive claim of non-existence.

---

## 15. Per-app research flow

### Step 1: Resolve product identity

Inputs:

- App name.
- Website hint.
- Category.
- Notes.

Output:

- Canonical product name.
- Trusted initial domain or domains.
- Identity status.
- Any ambiguity requiring review.

Do not search by app name alone when the name is generic.

Include the website hint in every identity-sensitive query.

### Step 2: Generate focused searches

Use three standard search intents.

#### API and authentication

```text
site:<trusted-domain> <app-name> developer API authentication OAuth API key
```

#### Access and gating

```text
site:<trusted-domain> <app-name> API credentials developer account pricing trial approval partner
```

#### MCP

```text
"<app-name>" official MCP server
```

For open-source software, also search the official GitHub repository and organization.

When an app's official documentation is on a separate supplied domain, use that domain instead of forcing the marketing domain.

### Step 3: Rank candidate sources

Use deterministic scoring.

Possible scoring features:

- Exact or trusted domain match.
- Developer documentation path.
- Authentication-related path.
- Credential or access-related path.
- Pricing or plan path.
- MCP path.
- Official GitHub organization.
- Search rank.
- Duplicate URL penalty.
- Generic marketing page penalty.
- Third-party domain penalty.

Prefer two to four strong pages rather than ten weak pages.

Typical source set:

1. API overview.
2. Authentication page.
3. Credential, plan, access, or approval page.
4. MCP page when found.

### Step 4: Fetch selected pages through Composio

Use `COMPOSIO_SEARCH_FETCH_URL_CONTENT`.

Store:

- URL.
- Title.
- Returned text or structured content.
- Fetch timestamp.
- Content hash.
- Raw response path.
- Any fetch error.

Cache by normalized URL.

Do not fetch the same URL repeatedly across retries or apps unless explicitly forced.

### Step 5: Reduce source content before inference

Documentation pages can be very long.

The extraction input should include:

- Page title.
- URL.
- Important headings.
- Relevant content windows around terms such as:
  - API
  - OAuth
  - authentication
  - token
  - key
  - credentials
  - developer account
  - pricing
  - trial
  - approval
  - partner
  - admin
  - MCP
  - webhook
  - REST
  - GraphQL
- Enough surrounding text to preserve context.

Keep a configurable maximum per page and per app.

Do not discard the raw fetched page from run artifacts.

### Step 6: Structured extraction

Make one extraction request per app.

The system prompt must say:

- Use only the supplied source content.
- Do not use prior knowledge.
- Return `unknown` when the sources do not support a field.
- Multiple auth methods may coexist.
- Separate developer signup from production access.
- Do not claim that an MCP does not exist.
- Cite evidence with supplied source IDs.
- Keep the description to one line.
- Do not decide buildability through intuition.

The model may propose a buildability value, but deterministic code must calculate the final value.

### Step 7: Deterministic validation

Check at least:

- Pydantic validation passes.
- App ID and identity match the input.
- Required fields are present.
- Enum values are valid.
- The description is one line.
- Every non-unknown material claim has evidence.
- Evidence source IDs exist.
- Evidence URLs were fetched.
- Official-source labels match the domain policy.
- `api_availability=no` has explicit evidence.
- `mcp_status=not_found` is described as a search result, not universal proof.
- `buildability=yes` has at least one real integration path.
- No claims conflict with each other.
- Auth notes agree with auth enums.
- API breadth agrees with availability.
- `api_breadth=none` is not paired with public protocols.
- A gated production path does not appear as fully self-serve.
- Browser-only evidence is marked.
- Third-party-only records are flagged.

### Step 8: Compute the buildability verdict

Use a deterministic function based on extracted fields.

Example logic:

```python
def compute_buildability(record: AppResearch) -> Buildability:
    usable_surface = (
        record.api_availability in {ApiAvailability.YES, ApiAvailability.LIMITED}
        or record.mcp_status in {McpStatus.OFFICIAL, McpStatus.COMMUNITY}
        or ApiProtocol.CLI in record.api_protocols
    )

    if not usable_surface:
        if record.api_availability == ApiAvailability.NO:
            return Buildability.NO
        return Buildability.UNKNOWN

    hard_gates = {
        DeveloperAccess.PARTNER_ONLY,
        DeveloperAccess.CONTACT_SALES,
        DeveloperAccess.NOT_AVAILABLE,
    }

    conditional_gates = {
        ProductionGate.PAID_PLAN,
        ProductionGate.APP_REVIEW,
        ProductionGate.ADMIN_APPROVAL,
        ProductionGate.VENDOR_APPROVAL,
        ProductionGate.PARTNER_APPROVAL,
        ProductionGate.CONTACT_SALES,
        ProductionGate.CUSTOMER_ACCOUNT_REQUIRED,
    }

    if record.developer_access in hard_gates:
        return Buildability.CONDITIONAL

    if any(gate in conditional_gates for gate in record.production_gates):
        return Buildability.CONDITIONAL

    if record.api_breadth == ApiBreadth.NARROW:
        return Buildability.CONDITIONAL

    if record.api_capabilities.write == Ternary.NO:
        return Buildability.CONDITIONAL

    return Buildability.YES
```

The real function can be refined after the pilot.

Store both:

- Model-proposed verdict.
- Rule-computed verdict.

If they differ, flag the record and preserve the difference for later analysis.

### Step 9: Decide whether to escalate

Send an app to the verifier when any of these conditions is true:

- Identity is ambiguous.
- Authentication has no supporting evidence.
- Developer access is unknown.
- Production gating is unknown.
- API availability is negative.
- API breadth is unknown.
- Only a marketing page was found.
- Only third-party evidence was found.
- Official pages conflict.
- A page could not be fetched normally.
- The record has internal contradictions.
- Model verdict and rule verdict differ materially.
- Evidence coverage is below the threshold.
- The app is one of the manually designated difficult apps.

### Step 10: Run the MCP verifier

The verifier prompt should state:

```text
The supplied first-pass answer is an untrusted hypothesis.

Independently verify only the disputed fields.

Use the provided Composio tools.
Prefer official developer, support, pricing, and GitHub sources.
Use normal search and fetch first.
Use Browser Tool only when normal fetch cannot establish the answer.
Return corrected field values, supporting evidence, unresolved questions,
and a short explanation of each change.
Do not use prior knowledge.
Do not make definitive negative claims from failed search.
```

The verifier output should be a strict correction schema:

```python
class FieldCorrection(BaseModel):
    field: str
    old_value: object
    new_value: object
    reason: str
    evidence_source_ids: list[str]


class VerificationResult(BaseModel):
    app_id: int
    corrections: list[FieldCorrection]
    additional_evidence: list[Evidence]
    unresolved_questions: list[str]
    needs_human_review: bool
```

Store:

```text
draft record
verification result
merged final record
machine-readable diff
```

### Step 11: Browser fallback

Use the Browser Tool only when:

- Normal fetch returns unusable content.
- The docs require JavaScript rendering.
- Important information is behind tabs or interactive navigation.
- Search finds the page but the content fetch misses the relevant section.
- A developer portal requires non-authenticated interaction to reveal docs.
- The verifier needs to confirm a page visually.

Do not use the browser for every app.

Browser tasks should have:

- One narrow objective.
- A maximum execution time.
- A maximum number of retries.
- A requested structured final answer.
- A saved session or output artifact where available.

### Step 12: Persist immediately

After every app, save its current state.

A crash on app 73 must not require restarting apps 1 through 72.

---

## 16. Confidence and human-review rules

Do not rely only on the model's self-reported confidence.

Compute evidence coverage in code.

Suggested required evidence groups:

```text
identity
description
authentication
developer access and gates
API availability and surface
MCP search
buildability inputs
```

Example:

```python
coverage = supported_required_groups / total_required_groups
```

Suggested classification:

```text
high:
coverage >= 0.85, no conflicts, no third-party-only claims, no unsupported negatives

medium:
coverage >= 0.65, no critical conflict, but one or more material unknowns

low:
coverage < 0.65, identity ambiguity, unsupported negative, or conflicting sources
```

Set `needs_human_review=true` for:

- Low confidence.
- Ambiguous identity.
- Third-party-only evidence.
- Partner or sales gating without explicit official evidence.
- A final `no` verdict.
- A browser failure.
- Conflicting official sources.
- A record changed substantially by the verifier.
- Any app specifically selected for the later manual accuracy sample.

---

## 17. Concurrency, retries, budgets, and caching

### Concurrency

Start with:

```python
asyncio.Semaphore(5)
```

Increase to 6 or 8 only after a stable five-app run.

The bottleneck may be Composio rate limits, browser task capacity, or OpenAI rate limits rather than local CPU.

### Per-app budgets

Default maximums:

```text
3 standard search calls
1 optional recovery search
4 normal page fetches
1 browser task
1 verifier run
```

The budgets should be configurable.

### Retries

Use exponential backoff for:

- Temporary Composio errors.
- OpenAI rate limits.
- Network failures.
- Browser task polling.

Do not retry:

- Invalid input.
- Confirmed unsupported page.
- Pydantic errors caused by a bad prompt more than a small bounded number of times.
- Permanent authorization failures.

### Caching

Cache:

- Search query results.
- URL fetch results.
- Reduced page content.
- Extraction request hash and response.
- Verifier request hash and response.

Suggested cache keys:

```text
sha256(tool_name + normalized_arguments)
sha256(model + prompt_version + app_input + source_hashes)
```

### Resumability

Every run should have a manifest:

```json
{
  "run_id": "2026-08-21T...",
  "pipeline_version": "0.1.0",
  "started_at": "...",
  "apps_total": 100,
  "completed": [],
  "failed": [],
  "flagged": []
}
```

CLI flags should support:

```text
--limit
--ids
--category
--resume
--force
--concurrency
--skip-browser
--skip-verifier
```

---

## 18. Run artifact layout

Use a timestamped or named run directory.

```text
runs/
  <run_id>/
    manifest.json
    logs.jsonl

    search/
      001-salesforce.json
      ...

    sources/
      by-url/
        <sha256>.json
      app-index/
        001-salesforce.json

    reduced/
      001-salesforce.json

    drafts/
      001-salesforce.json

    validation/
      001-salesforce.json

    verification/
      001-salesforce.json

    diffs/
      001-salesforce.json

    final/
      001-salesforce.json
      results.json
      results.jsonl

    failures.jsonl
```

Raw and first-pass artifacts must be immutable within a run.

A correction creates a new artifact. It must not silently replace the draft.

---

## 19. Repository structure

Recommended structure:

```text
.
├── AGENTS.md
├── README.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
│
├── data/
│   └── apps.csv
│
├── docs/
│   ├── COMPOSIO_TAKEHOME_CONTEXT.md
│   └── composio-tool-schemas/
│
├── prompts/
│   ├── extract.md
│   └── verify.md
│
├── src/
│   └── integration_research/
│       ├── __init__.py
│       ├── cli.py
│       ├── settings.py
│       ├── models.py
│       ├── composio_session.py
│       ├── discovery.py
│       ├── source_selection.py
│       ├── fetching.py
│       ├── reduction.py
│       ├── extraction.py
│       ├── validation.py
│       ├── verdict.py
│       ├── verifier.py
│       ├── storage.py
│       └── pipeline.py
│
├── tests/
│   ├── fixtures/
│   ├── test_models.py
│   ├── test_source_selection.py
│   ├── test_validation.py
│   ├── test_verdict.py
│   └── test_storage.py
│
├── scripts/
│   └── bootstrap.sh
│
└── runs/
    └── .gitkeep
```

This is a guide, not a requirement to create unnecessary abstraction.

Combine small modules if that makes the implementation faster and clearer.

Do not create a framework layer for hypothetical future use.

---

## 20. Expected CLI

Define a project script in `pyproject.toml`:

```toml
[project.scripts]
research = "integration_research.cli:app"
```

Expected commands:

```bash
# Confirm configuration and Composio access
uv run research doctor

# Print or save the known Composio tool schemas
uv run research inspect-tools

# Run the five-app pilot
uv run research run --ids 61,22,31,90,98 --run-id pilot-v1

# Run a small prefix
uv run research run --limit 5

# Run all apps
uv run research run --all --concurrency 6 --run-id full-v1

# Resume an interrupted run
uv run research run --all --resume full-v1

# Retry failures
uv run research retry --run-id full-v1

# Verify records flagged by deterministic validation
uv run research verify --run-id full-v1 --flagged

# Merge and export final results
uv run research export --run-id full-v1
```

The exact command naming can differ, but the capabilities must exist.

---

## 21. Five-app pilot

Do not start the first development run on all 100 apps.

Use:

| App | Why it is in the pilot |
|---|---|
| GitHub | Clear, broad, self-serve developer platform |
| Twilio | Multiple auth and credential patterns |
| Google Ads | Difference between developer access, customer credentials, and production approval |
| PitchBook | Enterprise and sales-gated access |
| Mermaid CLI | Agent-callable local CLI without a normal SaaS REST API |

IDs:

```text
61,22,31,90,98
```

The pilot is successful only when:

- All five records pass Pydantic validation.
- Each material claim has a fetched source.
- The source-selection logic prefers official pages.
- The pipeline stores raw, draft, validation, and final artifacts.
- The buildability rules behave sensibly for API, gated, and CLI cases.
- At least one intentionally difficult case reaches the verifier.
- Rerunning the pilot uses the cache.
- Interrupting and resuming the pilot works.
- Tests pass.

Only then run the other 95 apps.

---

## 22. Difficult cases to expect

The following classes of apps are likely to cause failures:

### Generic names

Examples:

- Plain.
- Close.
- Front.
- Grain.
- Fathom.
- Consensus.
- Twenty.

Always anchor queries with the website hint.

### Enterprise APIs

Examples:

- DealCloud.
- PitchBook.
- Gladly.
- Salesforce Commerce Cloud.
- Snowflake.
- Ramp.
- Brex.

Developer documentation may exist while credentials remain customer-admin, enterprise, sales, or partner gated.

### Advertising APIs

Examples:

- Google Ads.
- Meta Ads.
- LinkedIn Ads.
- Pinterest.

A developer may be able to create an app, but production use can require review, developer tokens, business verification, customer accounts, or scopes.

### Open-source or local interfaces

Examples:

- Twenty.
- Sherlock.
- Mermaid CLI.

The absence of a hosted REST API does not automatically make the app unbuildable.

A local CLI or self-hosted API can still be agent-callable.

### Product versus platform mismatch

Examples:

- NotebookLM with a Gemini Enterprise API hint.
- YouTube Transcript referring to a third-party transcript API.
- Otter AI with an MCP hint.
- Devin with an MCP hint.
- Paygent Connect with an incomplete identity hint.

The system must research the named product, not substitute a related platform without stating the distinction.

### Inaccessible documentation

Some sites may require JavaScript, login, region access, or interactive navigation.

These should trigger browser fallback or human review, not fabricated conclusions.

---

## 23. Deterministic validation tests

At minimum, unit-test these cases.

### Evidence

- A known value without evidence fails.
- `unknown` can pass without claim evidence but must add an unresolved question.
- A source ID referenced by a claim must exist.
- A third-party source cannot be labeled official.
- Duplicate normalized URLs are deduplicated.

### Authentication

- Multiple auth methods are accepted.
- An empty auth list is rejected.
- `unknown` cannot coexist with confirmed methods unless explicitly allowed and documented.
- Auth notes must not contradict the enum values.

### API

- `api_availability=no` with `api_breadth=broad` fails.
- `api_breadth=none` with `REST` fails.
- `api_availability=yes` without a protocol or explanation is flagged.
- A local CLI can be usable when REST is absent.

### Gating

- Self-serve developer access can coexist with a production app-review gate.
- Partner-only access produces at least a conditional verdict.
- A paid-plan gate must not be summarized as free self-serve access.

### MCP

- `official` requires an official source.
- `community` requires a repository or source URL.
- `not_found` cannot use wording that claims universal non-existence.

### Buildability

- Broad public read/write REST API plus self-serve access returns `yes`.
- Broad API plus partner approval returns `conditional`.
- Narrow read-only export returns `conditional`.
- Explicitly absent interface returns `no`.
- Missing evidence returns `unknown`.
- CLI-only Mermaid-like tool can return `yes`.

### Storage

- Draft artifacts are not overwritten.
- Resume skips completed apps.
- `--force` creates a new attempt or explicit replacement artifact.
- Cache keys are deterministic.

---

## 24. Prompt design

### Extraction prompt requirements

Keep the prompt in:

```text
prompts/extract.md
```

It should include:

- Task and field definitions.
- Source-only policy.
- Unknown policy.
- Negative-claim policy.
- Auth multiplicity.
- Developer-access versus production-gate distinction.
- API-breadth definitions.
- MCP definitions.
- Evidence source-ID instructions.
- One short worked example if needed.

Do not put the entire 100-app list in every API request.

### Verifier prompt requirements

Keep the prompt in:

```text
prompts/verify.md
```

It should include:

- First pass is untrusted.
- Verify only disputed fields.
- Prefer first-party evidence.
- Search and fetch before browser.
- No prior knowledge.
- No unsupported negative claims.
- Return corrections and evidence.
- Preserve unresolved uncertainty.

Version both prompts.

Store prompt version in each record.

---

## 25. Human-in-the-loop design

Human work must be targeted, not a manual re-research of all 100 apps.

Phase 1 should produce a review queue:

```text
runs/<run_id>/human_review.csv
```

Suggested columns:

```text
app_id
app_name
reason
disputed_fields
current_values
evidence_urls
recommended_check
```

Typical review reasons:

- Identity ambiguity.
- Enterprise gate not explicit.
- Product and developer platform mismatch.
- Only third-party evidence.
- Browser task failed.
- Conflicting official pages.
- Final `no` verdict.
- Large verifier correction.
- Weak evidence coverage.

The final accuracy sample will later be stratified across:

- Easy self-serve APIs.
- Gated enterprise APIs.
- Ads APIs.
- Open-source and CLI tools.
- Apps with MCP.
- Apps with browser failures.
- Apps with initial verifier corrections.

---

## 26. Future verification design

This is not the current implementation focus, but Phase 1 must preserve the data needed for it.

Later create:

```text
verification/manual_gold.json
```

For a sample of approximately 12 to 20 apps, manually record field-level truth and official evidence.

Then compare:

1. First-pass draft versus manual gold.
2. Automated verified result versus manual gold.
3. Final corrected result versus manual gold.

Report:

- Field-level accuracy.
- Record-level exact match.
- Evidence validity.
- Unsupported-claim rate.
- Accuracy by field.
- Accuracy by app category.
- Number and type of corrections.
- Remaining unknowns.

Do not invent a high accuracy number.

The final case study must show real misses.

---

## 27. Time budget

The complete assignment has a 6 to 8 hour budget.

Suggested allocation for the entire assignment:

| Time | Work |
|---|---|
| 0:00 to 0:30 | Repo, dependencies, Composio setup, environment |
| 0:30 to 1:30 | Schemas, direct tool wrappers, five-app pilot |
| 1:30 to 2:00 | Fix schema and validation based on pilot |
| 2:00 to 3:30 | Full 100-app run with concurrency |
| 3:30 to 4:15 | Retry failures and run verifier |
| 4:15 to 5:15 | Manual sample and accuracy comparison |
| 5:15 to 6:30 | Pattern analysis and HTML case study |
| 6:30 to 7:15 | Deployment, README, cleanup, final checks |

This requires strict scope control.

### Phase 1 time-saving rules

- No database.
- No React application.
- No LangChain.
- No LangGraph.
- No CrewAI.
- No AutoGen.
- No generic agent framework.
- No 100-agent swarm.
- No dashboard.
- No browser automation for normal pages.
- No hand-written records except explicit manual verification later.
- No premature pattern analysis before stable results exist.

---

## 28. Implementation sequence for Codex

Codex should work in this order.

### Milestone 0: Environment

- Confirm Python 3.12 and `uv`.
- Confirm `OPENAI_API_KEY`.
- Confirm `COMPOSIO_API_KEY`.
- Confirm Composio CLI login.
- Confirm Composio Codex plugin.
- Create `.env.example`.
- Ensure secrets are ignored.
- Run a single Composio search smoke test.
- Run a single URL fetch smoke test.

### Milestone 1: Static foundations

- Create input CSV.
- Create Pydantic enums and models.
- Create settings.
- Create run storage.
- Add unit tests for models and storage.
- Commit.

### Milestone 2: Composio direct path

- Inspect actual tool schemas.
- Implement search wrapper.
- Implement fetch wrapper.
- Add normalized errors and retry.
- Add cache.
- Save raw outputs.
- Commit.

### Milestone 3: One-app extraction

- Implement source ranking.
- Implement page reduction.
- Implement OpenAI structured extraction.
- Run GitHub only.
- Inspect evidence manually.
- Add tests.
- Commit.

### Milestone 4: Five-app pilot

- Run IDs 61,22,31,90,98.
- Fix schema and prompts.
- Implement verdict rules.
- Implement deterministic validation.
- Confirm resume and cache.
- Commit.

### Milestone 5: Verifier

- Expose restricted Composio MCP.
- Implement structured verifier agent.
- Force one pilot app through it.
- Save correction and diff.
- Confirm it does not have OpenAI web search.
- Commit.

### Milestone 6: Full run

- Run all 100 with low initial concurrency.
- Monitor failures.
- Retry only failed or flagged records.
- Export final JSON and JSONL.
- Do not begin presentation work until output quality is checked.

---

## 29. Initial prompt to give Codex

Use this after the repository and environment are prepared:

```text
Read docs/COMPOSIO_TAKEHOME_CONTEXT.md completely before changing code.

Implement Phase 1 only: the evidence-backed 100-app research pipeline.
Do not build the HTML case study yet.

First inspect the repository, installed package versions, and the exact
Composio schemas for the approved tools. Do not guess tool arguments.

Use Python 3.12 and uv.

Core requirements:
1. Read data/apps.csv.
2. Use a restricted reusable Composio session.
3. Use COMPOSIO_SEARCH_WEB and COMPOSIO_SEARCH_FETCH_URL_CONTENT for the normal path.
4. Use OpenAI only for structured inference over fetched content.
5. Do not use OpenAI web search.
6. Add deterministic source ranking, validation, buildability rules, cache,
   retry, concurrency, and resumable run artifacts.
7. Keep draft and final output separate.
8. Add an MCP verifier with Composio Search and Browser Tool only for
   flagged records.
9. Start with app IDs 61,22,31,90,98.
10. Do not run all 100 until the pilot and tests pass.

Before implementing, write a short implementation plan tied to the existing
files. Then implement milestone by milestone, running tests and the pilot
as you go. Keep the code direct and avoid unnecessary frameworks.
```

---

## 30. Root AGENTS.md guidance

Do not copy this entire long document into `AGENTS.md`.

The root `AGENTS.md` should be short and point to this file.

Recommended contents:

```markdown
# AGENTS.md

## Required context

- Read `docs/COMPOSIO_TAKEHOME_CONTEXT.md` completely before changing code.
- The current scope is Phase 1 only unless the user explicitly expands it.

## Engineering rules

- Use Python 3.12 and `uv`.
- Use Composio Search and Browser Tool for web access.
- Use OpenAI only for inference over fetched sources. Do not use OpenAI web search.
- Inspect installed Composio tool schemas before writing arguments. Never guess them.
- Preserve raw, draft, verification, diff, and final run artifacts separately.
- Every material non-unknown claim must have fetched evidence.
- Use deterministic validation and buildability rules.
- Do not add LangChain, LangGraph, CrewAI, AutoGen, a database, or a frontend in Phase 1.

## Verification before completion

- Run `uv run ruff check .`
- Run `uv run pytest`
- Run the five-app pilot for IDs `61,22,31,90,98`
- Confirm cache and resume behavior
- Do not run all 100 until the pilot is inspected
```

---

## 31. Environment variables

Create `.env.example`:

```dotenv
OPENAI_API_KEY=
COMPOSIO_API_KEY=

OPENAI_MODEL_EXTRACT=gpt-5.6-luna
OPENAI_MODEL_VERIFY=gpt-5.6-terra

COMPOSIO_USER_ID=composio-takehome-research
COMPOSIO_SESSION_ID=

RESEARCH_CONCURRENCY=5
RESEARCH_MAX_SEARCHES_PER_APP=4
RESEARCH_MAX_FETCHES_PER_APP=4
RESEARCH_MAX_BROWSER_TASKS_PER_APP=1
RESEARCH_MAX_VERIFIER_RUNS_PER_APP=1
RESEARCH_MAX_CHARS_PER_PAGE=20000
RESEARCH_MAX_CHARS_PER_APP=60000
```

The application may write a reusable session ID to `.state/` rather than requiring it in `.env`.

Never commit real keys or session headers.

---

## 32. README expectations

The final repository README will later need:

1. What the system does.
2. Architecture diagram.
3. Why direct SDK plus MCP fallback was selected.
4. Setup requirements.
5. Environment variables.
6. How to run the five-app pilot.
7. How to run all 100.
8. How to resume and retry.
9. Output directory explanation.
10. How evidence and buildability are calculated.
11. How verification works.
12. Known limitations.
13. Link to deployed case study.

Do not spend time polishing the README before the pipeline works.

---

## 33. Definition of done for Phase 1

Phase 1 is complete when:

- `data/apps.csv` contains all 100 apps.
- A reusable restricted Composio session works.
- Search and fetch calls use Composio.
- OpenAI produces strict structured records from fetched sources.
- OpenAI web search is absent.
- Source ranking and caching work.
- Every app result is persisted independently.
- The run can resume.
- Deterministic validation works.
- Buildability is calculated by code.
- Flagged records can be checked by a verifier agent through Composio MCP.
- Browser Tool is available as a bounded fallback.
- The five-app pilot passes and is manually inspectable.
- Tests and lint pass.
- Full-run output can be exported as JSON and JSONL.
- Drafts, corrections, and final records remain separately available.
- Failures and unknowns are reported honestly.

---

## 34. Non-goals for Phase 1

Do not:

- Build the final HTML page.
- Create charts.
- Write pattern conclusions before data exists.
- Claim an accuracy percentage.
- Manually fill all 100 rows.
- Add authentication flows for the researched apps.
- Actually connect accounts for the 100 apps.
- Build Composio toolkits for the apps.
- Use a vector database.
- Use a relational database.
- Build a distributed queue.
- Deploy the research runner.
- Optimize for production-scale millions of apps.
- Add abstractions that do not help finish the take-home.

---

## 35. Important engineering judgment

The strongest version of this assignment is not the one with the most agents.

It is the one where a reviewer can inspect a record and answer:

- Which page supported this field?
- Was that page official?
- Did the model infer more than the page said?
- Was production access confused with sandbox access?
- Was a negative conclusion actually proven?
- What changed during verification?
- Can the pipeline rerun and reproduce the result?
- Which cases still need a human?

The implementation should make those questions easy to answer.

---

## 36. Official implementation references

Use the installed package versions and official documentation as the source of truth.

- Composio CLI: https://docs.composio.dev/docs/cli
- Composio sessions: https://docs.composio.dev/docs/how-composio-works
- Composio session configuration: https://docs.composio.dev/docs/configuring-sessions
- Composio sessions over MCP: https://docs.composio.dev/docs/sessions-via-mcp
- Composio Search toolkit: https://docs.composio.dev/toolkits/composio_search
- Composio Browser Tool: https://docs.composio.dev/toolkits/browser_tool
- OpenAI structured outputs: https://developers.openai.com/api/docs/guides/structured-outputs
- OpenAI Agents SDK tools and Hosted MCP: https://openai.github.io/openai-agents-python/tools/
- OpenAI Agents SDK structured output: https://openai.github.io/openai-agents-python/agents/
- Codex `AGENTS.md`: https://developers.openai.com/codex/agent-configuration/agents-md
- Codex best practices: https://developers.openai.com/codex/learn/best-practices

---

## 37. Final instruction to Codex

Accuracy is more important than filling every field.

Use `unknown` when evidence is insufficient.

Never hide failures.

Do not proceed from a five-app pilot to all 100 until the pilot artifacts can be inspected and every important claim can be traced to a fetched page.
