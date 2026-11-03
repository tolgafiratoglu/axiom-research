# AxiomResearch

**Energy & Materials Research Intelligence — Evidence-Driven Multi-Agent System**

**Status:** Architecture definition / pre-implementation  
**Build order:** [`RoadMap.md`](./RoadMap.md) — follow phases 0–9 in order; this README is the locked target, not a backlog.  
**Purpose:** A complete, interview-ready reference project demonstrating **Strands Agents, autonomous Swarm handoffs, MCP, remote A2A verification, revisioned evidence, and measurable multi-agent performance**.

## Vision

AxiomResearch (`axiom-research`) investigates difficult **energy-storage and materials-science** questions by connecting published research, calculated material properties, chemical records, and research datasets. It is **not** a paper summarizer and does **not** infer industrial readiness from a promising calculation or single laboratory result.

Its distinctive capability is to show **what a scientific claim is supported by, how the evidence was challenged, and whether an independent agent could reproduce the source check**. Every architectural component must have a demonstrable purpose in a live interview—not merely appear in a diagram.

The product has **one complete target architecture**, not an MVP/v1/v2 feature roadmap. Implementation tasks may be ordered by dependency, but the design is evaluated as a single finished system.

## Research Scope

Focus on battery technologies, energy-storage materials, solid-state electrolytes, sodium-ion versus lithium-ion chemistry, material stability, and the gap between **computational predictions, experimental observations, and commercial feasibility**.

The research workflow may encounter publications from other disciplines, but it does not claim to be a general-purpose biomedical or all-science assistant. Clinical-trial systems and unrelated scientific data providers are deliberately excluded.

## User Experience

One Next.js screen, one conversation, **one WebSocket**. No SSE, no extra `POST /chat` plus a second event channel, no per-agent dashboards.

```text
┌─────────────────────────────────────────────┐
│  FINAL ASSESSMENT  (sticky viewport chrome) │
│  running: who is active, claim counts       │
│  done: conclusions, citations, disputes     │
├─────────────────────────────────────────────┤
│  investigation thread (only this scrolls)   │
│    user question                            │
│    typed events: handoff, tool, claim, A2A  │
├─────────────────────────────────────────────┤
│  input                                      │
└─────────────────────────────────────────────┘
```

- Users ask a question and follow up in the same thread (“What about sodium-ion batteries?”).
- Agents write **into the thread** as compact typed events, not long private essays. Local Swarm handoff and remote A2A verification must be visually distinct.
- The **Final Assessment** is a sticky panel at the top of the viewport, not the first message in the scrollback. While the run is in progress it shows status only — never a draft conclusion. When the gate passes, the Finalizer result appears there once.
- The Finalizer answer is **not** duplicated as a second assistant bubble at the bottom. The thread gets a short system line: the assessment is above.
- Claims expand **inline** in the same flow (DOI / arXiv ID / Materials Project ID / dataset DOI, version, units, retrieval time, method, license, verification status). No second evidence column.
- Group noisy tool calls; show summaries rather than raw JSON. Never expose private chain-of-thought.
- On follow-up, the sticky panel returns to in-progress for the new run. The previous assessment is pinned into the thread as a collapsed history card so earlier verdicts remain inspectable.

## Runtime and Deployment

**Core LLM:** Gemini Flash via Google’s API (`LLM_PROVIDER=gemini`). The concrete model ID is **only** `GEMINI_MODEL` — a currently supported Flash ID from [Google AI for Developers](https://ai.google.dev/gemini-api/docs/models). Do not hard-code IDs in source. As of the 2026-10-30 Gemini API changelog, `gemini-3.5-flash` is deprecated and requests are routed to `gemini-3.6-flash`; set `GEMINI_MODEL` to a live Flash model (for example `gemini-3.6-flash` or later), not Flash-Lite. Secrets live in the same file as Travel RAG and NASA MCP: `GEMINI_API_KEY` in `~/.config/rag/.env`. Swarm, Challenger, Verifier, and Finalizer share this one hosted model. Gemini itself is **not** containerized.

**Everything else that we run** is a Docker Compose service. Compose is the orchestration; Kubernetes, Kafka, and extra “platform” brokers are out of scope.

```text
                         Gemini Flash (hosted API, GEMINI_MODEL)
                                  ^
           api + verifier + (optional eval runner) call it
                                  |
┌─────────────────────────────────┴─────────────────────────────────┐
│ Docker Compose                                                    │
│                                                                   │
│  web (Next.js)  --WebSocket-->  api (FastAPI)                     │
│                                   |  local Strands Swarm           │
│                                   |  gate + tool-less Finalizer    │
│                                   |  ledger tools + calc tools     │
│                                   |                                │
│                                   +-- A2A --> verifier             │
│                                   |           separate container,  │
│                                   |           fresh context,       │
│                                   |           own MCP clients      │
│                                   |                                │
│     mcp-literature   mcp-materials   mcp-research-data             │
│     (MCP HTTP)       (MCP HTTP)      (MCP HTTP)                    │
│                                   |                                │
│                               postgres                             │
│                        sessions + Evidence Ledger                  │
└───────────────────────────────────────────────────────────────────┘

External scientific APIs (OpenAlex, Crossref, arXiv, Materials Project,
PubChem, Zenodo, DataCite) stay outside the compose file, same as Gemini.
```

| Service | Runs | Notes |
| --- | --- | --- |
| `web` | Next.js UI | Talks only to `api` over WebSocket. |
| `api` | FastAPI + local Swarm + gate + Finalizer | Single process for exploratory Swarm. Owns the socket, budgets, and ledger writes. |
| `verifier` | Independent Verifier as an A2A server | Separate container so it cannot see Swarm memory. Invoked by application code after Swarm, **not** as a Swarm node (`A2AAgent` is not supported inside Swarm). |
| `mcp-literature` | OpenAlex, Crossref, arXiv tools | Real MCP server, HTTP/streamable transport (not STDIO). |
| `mcp-materials` | Materials Project, PubChem tools | Same. |
| `mcp-research-data` | Zenodo, DataCite tools | Same. |
| `postgres` | Sessions, ledger, traces, eval records | Simple durable store; not a data platform. |

MCP servers are Docker services because agent ≠ API and because STDIO subprocesses do not cross container boundaries. `api` and `verifier` open **independent MCP clients** to the same three servers; they do not share a Swarm transcript. Do not duplicate MCP containers just to look more distributed.

## Architecture

```text
Next.js (web)
    |  WebSocket (single session socket)
    v
FastAPI (api): sessions, run control, budgets, audit events
    |
    +--> Strands Swarm (in-process)
    |      Research Planner -- autonomous handoff -->
    |      Investigator <--> Data Analyst <--> Challenger
    |           |                  |                  |
    |      approved MCP HTTP    local calc tools   ledger only
    |           \__________________|_________________/
    |                              |
    |                    Evidence Ledger (postgres)
    |                 (claims, sources, revisions,
    |                  calculations, hypotheses)
    |
    +--> Deterministic Verification Gate
    |           |   checks current ledger snapshot
    |           +---- A2A ----> verifier container
    |                           fresh context, independent MCP HTTP
    |           <---- typed verification records ----+
    |           |
    |           +--> revision and coverage policy
    |
    +--> Tool-less Finalizer (only after passing policy)
```

**WebSocket contract (one socket per session):**

| Direction | Messages |
| --- | --- |
| Client → server | `ask`, `cancel` |
| Server → client | Stable UI events: `agent.started`, `agent.handoff`, `tool.summary`, `evidence.updated`, `hypothesis.created`, `a2a.verification`, `verification.gate`, `answer.final`, `run.failed` |
| Both | Heartbeat; reconnect resumes from `last_event_id` without restarting a live run |

Normalize Strands SDK event field names at the `api` boundary. The browser never binds to unverified SDK keys.

**Three separate mechanisms, three distinct reasons:**

| Mechanism | Why it exists |
| --- | --- |
| **Strands Swarm** | Local specialists transfer control autonomously via `handoff_to_agent`, not a pre-scripted supervisor chain. |
| **MCP** | Standardized access to external scientific data; **an agent is not an API wrapper**. |
| **A2A** | The remote Verifier is a separately running agent with isolated context and its own read-only data access. |

The Verifier is **not a Swarm node**. The application invokes it across the A2A boundary as a mandatory post-Swarm check. Swarm determines the research path; deterministic code enforces the release policy. This intentionally avoids turning the exploratory Swarm into a fixed Graph.

## Agent Contracts

| Agent | Location | Produces | Tool access / boundaries |
| --- | --- | --- | --- |
| **Research Planner** | Local Swarm, entry point | Research questions, scope, success criteria, initial handoff | No MCP. Plans once; only revisits when the investigation is demonstrably blocked or reframed. Not a supervisor for every hop. |
| **Investigator** | Local Swarm | Source records, raw measurements, traceable claims, evidence links | Literature, Materials and Research Data MCP. Owns new retrieval and provenance. |
| **Data Analyst** | Local Swarm | Reproducible calculations, normalized comparisons, uncertainty notes | Ledger + deterministic local calculation tool. Requests missing records with a precise handoff to Investigator; does not independently redo broad research. |
| **Challenger** | Local Swarm | Alternative hypotheses, methodological objections, contradictions, specific follow-up questions | Ledger and existing evidence. Does not expand the domain or certify sources. |
| **Independent Verifier** | Remote A2A service (`verifier` container) | `verification` for current claim revisions, with independent source references | Separate read-only MCP clients (and provider API keys where required); never receives the Swarm transcript or prior agents' conclusions. Cannot alter research claims. |
| **Finalizer** | Outside Swarm, in `api` | Source-grounded final assessment, unresolved limitations | No external tools. Reads a policy-approved ledger snapshot only. |

Swarm agents may hand off in different orders depending on findings. **Meaningful collaboration** means that a handoff changes the next agent's task or the ledger—not merely that multiple API calls occurred.

Ledger writes are **local tools** (claim/evidence/hypothesis upsert, snapshot freeze), not free-form Swarm chat. Strands shared working context may carry claim IDs; it is not the Evidence Ledger.

## Scientific MCP Servers

Every server and tool below must do **real work in the canonical demonstration**. No placeholder servers and no APIs included only to inflate the technology list.

| Server | External source | Distinct responsibility |
| --- | --- | --- |
| **`mcp-literature`** | [OpenAlex](https://docs.openalex.org/), [Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/), [arXiv](https://info.arxiv.org/help/api/) | Find research and citation relationships; resolve DOI metadata; distinguish preprints, publication versions, and publisher records. |
| **`mcp-materials`** | [Materials Project](https://docs.materialsproject.org/downloading-data/using-the-api/getting-started), [PubChem PUG REST](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest) | Retrieve identifiable computed material properties and chemical compound metadata. Record methods, units and limitations rather than treating modeled properties as experimental outcomes. |
| **`mcp-research-data`** | [Zenodo](https://developers.zenodo.org/), [DataCite](https://support.datacite.org/docs/rest-api) | Locate associated deposited datasets and versioned records in Zenodo; independently resolve persistent dataset identifiers and metadata via DataCite. |

**Tool-permission model:** Investigator can discover and retrieve sources. Data Analyst primarily operates on already captured evidence and uses deterministic computation. Challenger reads the ledger. Remote Verifier may independently re-fetch the relevant source through its **own** MCP clients. Planner and Finalizer have no MCP access.

Providers require their own authentication, request quotas and data-use policies (e.g., Materials Project requires an API key). Tool responses must be validated and normalized; overlapping sources must have explicitly different purposes.

## Evidence Ledger: The Central Product Artifact

The ledger is not a transcript. It is a durable, structured, revision-aware record of scientific work. At minimum, model **sources, evidence, claims, calculations, hypotheses, verification records, and audit events**.

Illustrative claim (not a scientific assertion):

```json
{
  "claim_id": "claim-042",
  "revision": 3,
  "statement": "The cited calculation reports a material property in a specified range.",
  "author_agent": "data_analyst",
  "evidence_ids": ["ev-101", "ev-102"],
  "source_refs": ["materials-project:<record-id>", "doi:<identifier>"],
  "evidence_kind": "computed_property",
  "method": "As recorded by original source",
  "value": null,
  "unit": null,
  "verification_status": "pending",
  "verified_revision": null,
  "limitations": ["A calculation is not experimental or commercial validation"]
}
```

**Required semantics:**

- Every cited claim links to inspectable **source identifiers, original URLs, versions, retrieval timestamps, methods, units, and license metadata**.
- Scientific evidence types are never conflated: **preprint ≠ peer-reviewed publication; calculation ≠ measurement; correlation ≠ causation; a laboratory result ≠ commercial readiness**.
- Calculations must record inputs, formula, normalization steps, units, and output so they can be replayed deterministically.
- Challenger records hypotheses as hypotheses, not quietly promoted facts. Verifier records **source support and consistency**, not a guarantee of universal scientific truth.
- New evidence or edits increment the relevant revision / evidence fingerprint and invalidate stale verification. Results are tied to **exact revisions** and immutable source snapshots where permitted.
- Preserve three distinct contexts: **Swarm shared working context**, **durable Evidence Ledger**, and **conversation session memory** for follow-up questions.

## Independent Verification Gate

1. Swarm finishes normally or stops on a configured limit. The run status is recorded accurately.
2. Application code freezes a **ledger snapshot** and identifies all claims proposed for the final assessment.
3. Any claim with no **current** independent verification is submitted to Remote Verifier through **A2A**, with claim text, source identifiers and explicit criteria—not the Swarm dialogue, other agents' rationales, or prior verdicts.
4. The remote agent re-fetches relevant evidence via its own MCP access and returns one of: `verified`, `rejected`, `insufficient_evidence`, `conflicting_evidence`, with source-level references and the verified revision.
5. Deterministic code verifies the result schema, ledger revision, completeness, policy and source reachability. A successful A2A transport request is **not** equivalent to scientific verification.
6. Only then may the tool-less Finalizer compose the answer from eligible claims. Rejected, insufficient or conflicting findings may be discussed **only with their status clearly labeled**, never stated as established facts.

**Failure rule:** On timeout, exhausted handoffs, unreachable Verifier or stale verification, do not claim success. Return a clear run/verification status through the UI. Do not generate a falsely confident final answer. The gate is enforced in code, not left to an LLM prompt.

## Runtime, Reliability and Security

- Explicit `max_handoffs`, `max_iterations`, `execution_timeout`, node timeouts, and repetitive handoff detection; set limits **tighter than SDK defaults** (do not ship `max_handoffs=20` / 15-minute execution). Enforce a **per-question token and cost ceiling**.
- Each MCP server has defined tool schemas, response validation, rate limiting, timeouts, retry policy and meaningful failure events. Provider API keys stay in the secrets file / mounts, not in images. There is **no product auth** layer on MCP, `api`, or `web` (Compose binds localhost).
- Treat titles, abstracts, dataset descriptions and MCP responses as **untrusted data**; defend against prompt injection and prohibit text retrieved from sources from changing permissions or system instructions.
- Keep request/run IDs, agent IDs, event ordering, timestamps, cost, token usage, and trace IDs. Store audit trails without exposing private chain-of-thought.
- `api` remains a session/run gateway. Compose services exist to isolate Verifier, MCP, and storage — not to justify a mesh.
- **Tests never make outbound network calls.** Anything under `tests/` (and CI `pytest`) uses fixtures, mocks, and in-process fakes only — no live Gemini, no scientific provider APIs (OpenAlex, Crossref, arXiv, Materials Project, PubChem, Zenodo, DataCite, …), no live A2A Verifier, no external HTTP. Optional live checks belong in operator-only scripts (for example `scripts/mcp_live_smoke.py`) or a separately documented demo/eval path — never in the default test suite.

## Licensing and Research Integrity

- API availability does **not** imply unrestricted storage, full-text use, embedding, training, redistribution or public display rights.
- Keep bibliographic metadata separate from article full text. **Do not automatically download or vector-index copyrighted PDFs or abstracts.** No persistent RAG store is needed for this product.
- Inspect provider terms and item-level licenses; retain attribution, provenance and permitted-use metadata. Restrict cache/storage/redistribution by policy.
- Present versioned preprints and computed datasets with their scientific status and limitations; do not turn estimates into discoveries.
- AxiomResearch is a research decision-support and evidence-tracing tool, not a substitute for domain expert review.

## Evaluation: Prove That Multi-Agent Collaboration Helps

Ship repeatable evaluations comparing **the complete Swarm system against one agent using the same MCP tools**, under stated cost and time budgets. Maintain two evaluation modes: reproducible fixture/snapshot-based runs and a live-API demonstration.

Unbundle the comparison so Swarm is not credited for the Verifier:

1. One agent + same MCP, no gate.
2. One agent + same MCP + A2A gate.
3. Swarm + A2A gate.

Use a small, carefully curated **gold set** with explicit expected checks (not just broad LLM-as-judge scores):

- A fabricated DOI or a DOI resolving to an unrelated paper.
- A preprint incorrectly described as peer-reviewed work.
- Two numerical results with incompatible units or measurement conditions.
- A computed stability metric incorrectly described as experimentally established.
- A single experiment used to claim commercial-scale readiness.
- A planted alternative explanation that should trigger a Challenger handoff.
- An updated claim after verification (**stale-verification regression test**).
- An MCP outage and a failed or delayed remote A2A verification.

Measure **citation validity, claim-to-source support, planted-error detection, verification coverage, handoff usefulness, redundant tool calls, latency, token cost, and graceful failure behavior**. Any qualitative methodology score must have human-reviewed rubrics; an LLM judge alone is not ground truth.

## Canonical Live Demonstration

**Question:** “Can solid-state batteries realistically replace conventional lithium-ion batteries? What do published studies, computed materials data, and deposited research datasets actually support?”

A successful demo shows:

1. Planner defines the question and hands off without supervising every turn.
2. Investigator calls Literature, Materials and Research Data **MCP** tools and writes traceable source/evidence records.
3. Data Analyst normalizes units and compares relevant inputs using a **local deterministic calculation tool**; missing data triggers a specific Investigator handoff.
4. Challenger raises an alternative hypothesis or highlights a methodological gap; the Swarm may revisit investigation autonomously.
5. The **remote A2A Verifier**, in its own container, independently re-fetches evidence and emits revision-bound verdicts.
6. The deterministic gate rejects stale / missing verification; the sticky Final Assessment shows only supportable conclusions and explicit uncertainties.
7. One WebSocket conversation differentiates **Swarm handoff, MCP call, and A2A verification**. The live gold-path hits known records on all three MCP servers (including a PubChem compound and a Zenodo/DataCite dataset PID).

**Scientific guardrail:** A calculated material property is not proof of manufacturing feasibility, operational safety, cost competitiveness or market adoption.

## Architectural Boundaries

- **Not** a general clinical/biomedical research platform.
- **Not** a collection of one-API-per-agent wrappers or a fixed routing Graph disguised as a Swarm.
- **Not** a generic paper summarizer or another Travel RAG project with different documents.
- **Not** an SSE telemetry console (that is NASA MCP) and **not** a chat bubble that is also the final answer (that is Travel RAG).
- **Not** Kubernetes, Kafka, or unused MCP replicas. Docker Compose is the runtime.
- **Not** a local LLM stack: Qwen/Ollama/Bedrock are out unless a measured comparison demands them.
- **Not** a sequence of MVPs; this README describes the **single complete target system**.

## Primary Technical References

- [Strands Swarm](https://strandsagents.com/docs/user-guide/sdk/multi-agent/swarm/)
- [Strands A2A](https://strandsagents.com/docs/user-guide/sdk/multi-agent/agent-to-agent/)
- [Strands Multi-Agent Patterns](https://strandsagents.com/docs/user-guide/sdk/multi-agent/multi-agent-patterns/)
- Official provider API documentation is linked in the MCP table above.
