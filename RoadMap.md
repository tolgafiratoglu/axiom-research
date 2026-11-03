# AxiomResearch — RoadMap

This is the **implementation order** of the single target system in [`ReadMe.md`](./ReadMe.md). It is not an MVP/v1/v2 product cut.

**How this map is used**

- Implement **one phase at a time**, in numeric order. Do not start Phase N+1 while Phase N exit criteria are open.
- Finish a **subsection** (e.g. 1.B) before opening the next subsection in the same phase.
- Checkboxes are the source of progress. Mark `[x]` only when the item is in the tree and its tests (if listed) pass.
- If a change would violate [`ReadMe.md`](./ReadMe.md) boundaries, change the README first — do not “just ship it”.
- **No outbound network from tests** (see [`ReadMe.md`](./ReadMe.md) Runtime rule). `tests/` / `pytest` use fixtures and mocks only — never live Gemini, scientific APIs, or live A2A. Live smoke (1.15), Inspector, eval live runner, and `DEMO.md` are **operator-only**, not CI.
- Agent runs **only** the fixture named on the current item (`pytest` that file, once). Operator runs `docker compose up`, live smoke (1.15), Inspector, eval live runner, and `DEMO.md`.
- Ports, Swarm budget numbers, npm names, and MCP directory names recorded in **0.A** stay unless the README changes.

**Locked decisions (do not revisit during build)**

| Decision | Value |
| --- | --- |
| Name | **AxiomResearch**. Repo directory, Compose project, npm, and Docker image prefixes: `axiom-research`. Python import path `axiom_research`. Never “Science Council”. |
| LLM | `LLM_PROVIDER=gemini`. Model ID comes from `GEMINI_MODEL` (a currently supported Gemini Flash ID). Do not hard-code retired IDs such as `gemini-3.5-flash`. |
| Secrets | `GEMINI_API_KEY` in `~/.config/rag/.env` |
| Transport | One WebSocket per session. No SSE. No `POST /chat` event channel. |
| Runtime | Docker Compose for everything we run. Gemini and scientific APIs stay hosted. |
| MCP | Three HTTP MCP servers. Not STDIO. |
| Swarm | Planner, Investigator, Data Analyst, Challenger in `api`. |
| Verifier | Separate `verifier` container, A2A, not a Swarm node. |
| UI | Single column: sticky Final Assessment + typed investigation thread. |

---

## 0. Foundation

Repo, Compose skeleton, config, shared contracts. No agents yet.

### 0.A Layout and tooling

- [x] **0.1** Repository layout:

  ```text
  api/            FastAPI + Swarm + gate + Finalizer
  verifier/       A2A Independent Verifier
  mcp/            literature, materials, research_data servers
  web/            Next.js App Router
  packages/axiom_research/  shared Pydantic event + ledger schemas
  eval/           gold set + runners
  tests/          unit/integration (no live LLM/API)
  ```

- [x] **0.2** Python package metadata (`pyproject.toml`, import `axiom_research`), ruff/pytest, Node workspace for `web` (`name: axiom-research`).
- [x] **0.3** `.env.example`: `LLM_PROVIDER=gemini`, `GEMINI_MODEL` (operator-chosen supported Flash ID; no retired default), `SECRETS_ENV_PATH=~/.config/rag/.env`, service URLs, Swarm budget defaults. Comment the Google AI for Developers model list; as of 2026-10-30 `gemini-3.5-flash` is deprecated and routed to `gemini-3.6-flash`.
- [x] **0.4** Root `docker-compose.yml` with `name: axiom-research` and **named services only** (can be `sleep`/health stubs): `web`, `api`, `verifier`, `mcp-literature`, `mcp-materials`, `mcp-research-data`, `postgres`.

**0.A recorded defaults** (tree + `.env.example`; do not re-pick in 3.8 / 7.6):

| Item | Value |
| --- | --- |
| Host ports (`127.0.0.1`) | web `3200`, api `8200`, verifier `8201`, mcp `8210–8212`, postgres `5434` |
| WS (browser) | `NEXT_PUBLIC_WS_URL=ws://127.0.0.1:8200/ws/session` |
| Swarm | `max_handoffs=8`, `max_iterations=8`, execution `180s`, node `45s`, repetitive handoff on, `100000` tokens, `$1.00` |
| npm | root workspace `axiom-research`; `web` package `axiom-research-web` |
| MCP dirs | `mcp/literature`, `mcp/materials`, `mcp/research_data` |
| Tooling also in tree | `.gitignore` (keep `.cursor/rules`); `.cursor/rules/axiom-research.md` |
| Gemini | `GEMINI_MODEL` in project `.env`; `GEMINI_API_KEY` only from `SECRETS_ENV_PATH=~/.config/rag/.env` (not project `.env` / process env); loader in `packages/axiom_research/settings.py` |

**0.A done.** 0.B schemas and contract tests are in `packages/axiom_research` + `tests/test_contracts.py`.

### 0.B Shared contracts

- [x] **0.5** Pydantic models for WebSocket envelopes: client `ask` / `cancel`; server `agent.started`, `agent.handoff`, `tool.summary`, `evidence.updated`, `hypothesis.created`, `a2a.verification`, `verification.gate`, `answer.final`, `run.failed`; heartbeat + `last_event_id`.
- [x] **0.6** Ledger record types: source, evidence, claim, calculation, hypothesis, verification, audit event (revision + fingerprint fields included).
- [x] **0.7** Agent identity enum: `planner`, `investigator`, `data_analyst`, `challenger`, `verifier`, `finalizer`.

**Exit:** `docker compose config` succeeds; contract tests import schemas; no Gemini/MCP calls.

---

## 1. Scientific MCP servers

Real tools, HTTP transport, Docker. Empty servers are not allowed.

### 1.A Transport and server skeleton

- [x] **1.1** MCP HTTP/streamable server skeleton (one shared runner used by all three).
- [x] **1.2** Timeout, retry, schema validation, rate-limit, structured errors. Treat payloads as untrusted. No product auth on MCP/api/web.
- [x] **1.3** Policy: metadata only — no PDF/abstract bulk download, no vector index.

### 1.B `mcp-literature`

- [x] **1.4** OpenAlex: search works, citation relationships, identifiers.
- [x] **1.5** Crossref: DOI metadata resolve.
- [x] **1.6** arXiv: preprint vs later publication distinction.
- [x] **1.7** Fixture tests for each tool (recorded JSON). Distinct purpose of the three APIs documented on the tool descriptions.

### 1.C `mcp-materials`

- [x] **1.8** Materials Project: identifiable computed properties, methods, units, limitations.
- [x] **1.9** PubChem PUG REST: compound metadata.
- [x] **1.10** Never label computed properties as experimental. Fixture tests.

### 1.D `mcp-research-data`

- [x] **1.11** Zenodo: deposited records, versions, licenses.
- [x] **1.12** DataCite: independent PID/metadata resolve (Verifier path).
- [x] **1.13** Fixture tests. Zenodo vs DataCite purposes stay distinct.

### 1.E Compose wiring

- [x] **1.14** Three MCP services healthy in Compose; `GET`-style health on each.
- [x] **1.15** Optional live smoke script (manual, not CI): one call per provider with real keys.

**Exit:** all MCP tools have fixture tests; Compose brings three servers up; operator (not agent) can list tools with Inspector or equivalent.

---

## 2. Evidence Ledger

Durable structured store. Swarm chat is not the ledger.

### 2.A Persistence

- [x] **2.1** Postgres schema + migrations for sessions, runs, ledger tables, event log, traces, eval records.
- [x] **2.2** Snapshot freeze: immutable copy of claim/evidence revisions used for a gate/Finalizer pass.
- [x] **2.3** Revision increment invalidates `verification` bound to older fingerprint.

### 2.B Ledger tools (local, in `api`)

- [x] **2.4** Tools: upsert source, evidence, claim, calculation, hypothesis; attach evidence to claim; freeze snapshot; read current snapshot.
- [x] **2.5** Calculations store inputs, formula, units, output (replayable).
- [x] **2.6** Unit tests: stale verification after edit; hypothesis cannot be read as a claim; missing units rejected on numeric claims.

**Exit:** ledger round-trip tests pass against Compose Postgres; no LLM involved.
(`tests/test_ledger_tools.py` mocked; operator: `AXIOM_LEDGER_PG_TEST=1 pytest tests/test_ledger_postgres.py` after `postgres` + `axiom-db-migrate`.)


---

## 3. Strands Swarm (local)

Exploratory collaboration inside `api`. No Verifier, no UI.

### 3.A Model adapter

- [x] **3.1** Wire Strands `GeminiModel` to `axiom_research.settings` (travel-rag secrets load already in `packages/axiom_research`). Refuse to start if `GEMINI_MODEL` / `GEMINI_API_KEY` unset or empty. Do not bake a model ID into code. Flash family, not Flash-Lite.
- [x] **3.2** Token/cost accounting hook per agent turn.

### 3.B Agents and tools

- [x] **3.3** Research Planner: no MCP, no ledger writes except perhaps run scope; one-shot handoff; not a per-hop supervisor.
- [x] **3.4** Investigator: literature + materials + research-data MCP clients; owns retrieval + provenance writes.
- [x] **3.5** Data Analyst: **no MCP**; ledger read + deterministic local calculation tool; precise Investigator handoff when records are missing.
- [x] **3.6** Challenger: ledger only; writes hypotheses / contradictions; does not expand domain or certify sources.

### 3.C Swarm runtime

- [x] **3.7** `handoff_to_agent`; `entry_point=planner`.
- [x] **3.8** Budgets from 0.A: `max_handoffs=8`, `max_iterations=8`, `execution_timeout=180s`, `node_timeout=45s`. Repetitive handoff detection **on**.
- [x] **3.9** Per-question token/cost ceiling; stop with `run.failed` semantics when exceeded.
- [x] **3.10** CLI: `python -m api.cli "question"` prints node history + ledger summary (no Finalizer yet).
- [x] **3.11** Tests with mocked MCP + mocked Gemini: tool-visibility, planner-without-MCP, analyst-does-not-search, repetitive handoff stops.

**Exit:** CLI run against mocks shows at least one real `handoff_to_agent` and ledger rows; budgets enforced.
(`python -m api.cli --mock "…"`; unit: `tests/test_swarm_runtime.py`.)


---

## 4. FastAPI WebSocket gateway

The only frontend transport.

### 4.A Session and socket

- [x] **4.1** `WS /ws/session`: one socket per conversation. `ask` starts a run; `cancel` aborts; heartbeat.
- [x] **4.2** Event log persisted; reconnect with `last_event_id` replays missed events and **does not** restart a live run.
- [x] **4.3** Follow-up `ask` on the same session uses conversation memory + current ledger, not a blank Swarm.


### 4.B Event normalization

- [x] **4.4** Map Strands `multiagent_*` stream events → stable UI events from 0.5. Browser never sees raw SDK keys.
- [x] **4.5** Ledger tool completions emit `evidence.updated` / `hypothesis.created` (not raw JSON dumps).
- [x] **4.6** Tests: WS client fixture, replay, cancel, mapping table.

**Exit:** a mocked Swarm run streams the stable event set over WS; reconnect test passes.
(`tests/test_ws_normalize.py`; reconnect replay covered with mocked Swarm stream.)


---

## 5. Verification gate, A2A Verifier, Finalizer

This is the release boundary. Swarm must not write the user-facing answer.

### 5.A `verifier` service

- [x] **5.1** Strands `A2AServer` in its own container (`agent_factory` per context).
- [x] **5.2** Own MCP HTTP clients to the three servers. No Postgres claim writes. No Swarm transcript in the A2A payload.
- [x] **5.3** Returns only `verified` | `rejected` | `insufficient_evidence` | `conflicting_evidence` plus source refs + revision.
- [x] **5.4** Tests: payload without agent opinions; cannot mutate claims.


### 5.B Gate (deterministic, in `api`)

- [x] **5.5** After Swarm stop (success **or** budget), freeze snapshot; collect claims for the assessment.
- [x] **5.6** Send unverified **current** revisions to Verifier via `A2AAgent` (application code, not Swarm handoff).
- [x] **5.7** Reject stale verification, schema-invalid results, transport-success-without-science.
- [x] **5.8** Unreachable Verifier / timeout → `run.failed` / labeled incomplete assessment. **No confident Finalizer output.**

### 5.C Finalizer

- [x] **5.9** Tool-less agent (or strictly tool-less prompt) reads **policy-approved snapshot only**.
- [x] **5.10** Emits `answer.final`: conclusions, citations, disputed/insufficient items labeled, uncertainty. Guardrail: calculation ≠ commercial readiness.
- [x] **5.11** Tests: stale-verification regression; rejected claims cannot appear as facts; gate-fail does not produce a fake answer.

**Exit:** mocked end-to-end `ask` → Swarm → A2A → gate → `answer.final` (or honest failure) over WS.
(`tests/test_finalizer.py`; WS path with mocked Verifier client.)

---

## 6. Next.js UI

One screen, one socket. Not NASA’s three-column console, not Travel RAG’s answer-in-bubble.

### 6.A Shell

- [x] **6.1** App Router page: sticky Final Assessment, scrolling thread, input. Desktop + a usable narrow width.
- [x] **6.2** WebSocket client: `ask` / `cancel` / heartbeat / `last_event_id` resume.
- [x] **6.3** Assessment panel while running: status, active agent, claim counts — **never a draft answer**.
  (`web/`: App Router shell + `SessionSocket`; operator: `npm install` in `web`, copy `.env.local.example`, `npm run dev`.)

### 6.B Thread

- [x] **6.4** Render typed events: `handoff`, `tool.summary`, `claim`, `hypothesis`, `a2a.verification`, `verification.gate`, `run.failed`.
- [x] **6.5** Local handoff vs A2A visually distinct.
- [x] **6.6** Claim expand inline (identifiers, units, license, verification). No second column, no raw CoT, no tool JSON.
- [x] **6.7** `answer.final` fills the sticky panel once. Thread gets a one-line “assessment is above” — no duplicate bubble.
  (`web/components/Thread*.tsx`, `ClaimExpand.tsx`; `evidence.updated` display fields in normalize.)

### 6.C Follow-up

- [x] **6.8** New `ask` resets sticky panel to in-progress; previous assessment drops into the thread as a collapsed history card.
- [x] **6.9** Browser-verify the canonical question layout (sticky + stream + input) before closing the phase.
  (`AssessmentHistoryCard`; offline `?demo=layout` for sticky + stream + input check.)

**Exit:** UI walkthrough against mocked or local stack shows the seven demo beats from the README.
(`web/?demo=layout` — no live Gemini/scientific APIs.)

---

## 7. Hardening

Production-shaped, still Compose-only.

- [x] **7.1** Prompt-injection tests: hostile abstract/title cannot change instructions or tool permissions.
  (`packages/axiom_research/untrusted.py`; `tests/test_prompt_injection.py`.)
- [x] **7.2** MCP outage / 429 / timeout → `tool.summary` failure + gate-safe outcome, no fabricated sources.
  (`packages/axiom_research/mcp/failures.py`; normalize fail→`tool.summary`; `tests/test_mcp_failure_paths.py`.)
- [x] **7.3** Health: `api` liveness/readiness (Postgres + MCP reachability; Gemini is not a readiness blocker).
  (`api/health.py`; `/health`+`/health/live`+`/health/ready`; `tests/test_api_health.py`.)
- [x] **7.4** Provider API keys (e.g. Materials Project) only via secrets mount; not in images. No product auth layer.
  (`PROVIDER_SECRET_NAMES` / secrets-file-only loaders; `tests/test_secrets_policy.py`.)
- [x] **7.5** Run/trace IDs, latency, token cost on events (no private CoT stored).
- [x] **7.6** Compose `up` from a clean checkout documented in README (ports, env, Materials Project key).
  (`ReadMe.md` § Local Compose bring-up; ports / `.env` / `SECRETS_ENV_PATH` + `MP_API_KEY`.)

**Exit:** failure-path tests green; `docker compose up` documented and repeatable.

---

## 8. Evaluation

Prove collaboration; do not credit Swarm for the Verifier.

### 8.A Gold set

- [ ] **8.1** Small curated cases (fixtures): fabricated/wrong DOI; preprint-as-peer-review; unit mismatch; computed-as-experimental; single-lab-as-commercial; planted alternative for Challenger; stale-verification; MCP outage; delayed A2A.
- [ ] **8.2** Human rubric only where a metric is qualitative. No LLM-as-judge as ground truth.

### 8.B Runners

- [ ] **8.3** Fixture/snapshot runner (CI). Live-API runner (manual).
- [ ] **8.4** Three-way comparison, same tools and budgets: (1) one agent, no gate (2) one agent + A2A gate (3) Swarm + A2A gate.
- [ ] **8.5** Report: citation validity, claim-to-source, planted-error detection, verification coverage, handoff usefulness, redundant tools, latency, token cost, failure behavior.

**Exit:** `eval/` produces a checked-in sample report from fixtures.

---

## 9. Canonical demo lock

Interview-ready gold path.

- [ ] **9.1** Pin known live identifiers: OpenAlex/DOI, Materials Project record, PubChem compound, Zenodo record + DataCite PID for the solid-state battery question.
- [ ] **9.2** Scripted walkthrough `DEMO.md`: compose up, ask the canonical question, point at handoff / MCP / A2A / sticky assessment.
- [ ] **9.3** Confirm Verifier uses a **different** fetch path than Investigator for at least one PID (Zenodo vs DataCite).
- [ ] **9.4** Scientific guardrail visible in the Final Assessment text.
- [ ] **9.5** README status line updated from “pre-implementation” when 0–9 checkboxes for the demo path are done.

**Exit:** one operator can run the demo from `DEMO.md` without tribal knowledge.

---

## Out of order / out of scope

Do **not** add these while following this map:

- Extra MCP servers, Europe PMC, PubMed, ClinicalTrials, GDELT
- Qwen, Ollama, Bedrock, Flash-Lite as the core model
- SSE, REST chat, agent dashboards, evidence side-column
- LangGraph, Kafka, Kubernetes, persistent RAG / Qdrant / Neo4j
- Putting `A2AAgent` inside the Swarm
- Giving Data Analyst or Planner unrestricted MCP
- Duplicating MCP containers “for isolation theater”

Build order reminder: **0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9**.
The first user-visible vertical slice that is allowed to look “complete” is the end of **Phase 5** (WS + Swarm + gate + Finalizer). The UI in Phase 6 is the interview skin on that slice, not a second architecture.
