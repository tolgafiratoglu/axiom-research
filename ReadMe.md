
# Science Council

**Energy & Materials Research Intelligence — Evidence-Driven Multi-Agent System**

**Status:** Architecture definition / pre-implementation  
**Purpose:** A complete, interview-ready reference project demonstrating **Strands Agents, autonomous Swarm handoffs, MCP, remote A2A verification, revisioned evidence, and measurable multi-agent performance**.

## Vision

Science Council investigates difficult **energy-storage and materials-science** questions by connecting published research, calculated material properties, chemical records, and research datasets. It is **not** a paper summarizer and does **not** infer industrial readiness from a promising calculation or single laboratory result.

Its distinctive capability is to show **what a scientific claim is supported by, how the evidence was challenged, and whether an independent agent could reproduce the source check**. Every architectural component must have a demonstrable purpose in a live interview—not merely appear in a diagram.

The product has **one complete target architecture**, not an MVP/v1/v2 feature roadmap. Implementation tasks may be ordered by dependency, but the design is evaluated as a single finished system.

## Research Scope

Focus on battery technologies, energy-storage materials, solid-state electrolytes, sodium-ion versus lithium-ion chemistry, material stability, and the gap between **computational predictions, experimental observations, and commercial feasibility**.

The research workflow may encounter publications from other disciplines, but it does not claim to be a general-purpose biomedical or all-science assistant. Clinical-trial systems and unrelated scientific data providers are deliberately excluded.

## User Experience

- **Single Next.js screen; one continuous conversation.** Users ask a question, inspect the investigation, and ask contextual follow-ups such as “What about sodium-ion batteries?”
- A prominent **Final Assessment** panel at the top displays supported conclusions, citations, disputed points, and uncertainty. During investigation it shows an accurate in-progress state; it must never present a provisional claim as final.
- The conversation streams meaningful events: agent activity, **local Swarm handoffs**, MCP tool summaries, ledger changes, and **remote A2A verification**. Local handoff and networked A2A must be visibly distinct.
- Claims expand into their provenance: DOI / arXiv ID / Materials Project ID / dataset DOI, source version, units, retrieval time, method, license, and verification status.
- Group noisy tool calls; show useful summaries rather than raw JSON dumps. Never expose private chain-of-thought.

## Architecture

```text
Next.js: single conversation + final assessment + evidence inspection
           |  HTTP + SSE
           v
FastAPI: sessions, stream adapter, run control, budgets, audit events
           |
           +--> Strands Swarm (single local process)
           |      Research Planner -- autonomous handoff -->
           |      Investigator <--> Data Analyst <--> Challenger
           |           |                  |                  |
           |      approved MCP reads   local calc tools   ledger only
           |           \__________________|_________________/
           |                              |
           |                    Evidence Ledger
           |                 (claims, sources, revisions,
           |                  calculations, hypotheses)
           |
           +--> Deterministic Verification Gate
           |           |   checks current ledger snapshot
           |           +---- A2A request ----> Remote Verifier
           |                                 separate process, fresh
           |                                 context, independent MCP reads
           |           <---- typed verification records ----+
           |           |
           |           +--> revision and coverage policy
           |
           +--> Tool-less Finalizer (only after passing policy)
           |           |
           +--> persisted conversation + ledger + trace/eval records
```

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
| **Independent Verifier** | Remote A2A service | `verification` for current claim revisions, with independent source references | Separate read-only MCP connections and credentials; never receives the Swarm transcript or prior agents' conclusions. Cannot alter research claims. |
| **Finalizer** | Outside Swarm | Source-grounded final assessment, unresolved limitations | No external tools. Reads a policy-approved ledger snapshot only. |

Swarm agents may hand off in different orders depending on findings. **Meaningful collaboration** means that a handoff changes the next agent's task or the ledger—not merely that multiple API calls occurred.

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

- Explicit `max_handoffs`, `max_iterations`, `execution_timeout`, node timeouts, and repetitive handoff detection; enforce a **per-question token and cost ceiling**.
- Each MCP server has defined tool schemas, least-privilege credentials, response validation, rate limiting, timeouts, retry policy and meaningful failure events.
- Treat titles, abstracts, dataset descriptions and MCP responses as **untrusted data**; defend against prompt injection and prohibit text retrieved from sources from changing permissions or system instructions.
- Normalize SDK-specific Strands stream events to stable UI events: `agent.started`, `agent.handoff`, `tool.summary`, `evidence.updated`, `hypothesis.created`, `a2a.verification`, `verification.gate`, `answer.final`, `run.failed`.
- Keep request/run IDs, agent IDs, event ordering, timestamps, cost, token usage, and trace IDs. Store audit trails without exposing private chain-of-thought.
- Persist session and ledger records with a simple database. API gateway stays thin; no unrelated business microservices, Kafka or Kubernetes solely for architectural decoration.
- Use **configurable model providers** supported by the selected Strands SDK version. Do not require AWS Bedrock; provider choice must have a documented reason and measurable cost/quality tradeoff.

## Licensing and Research Integrity

- API availability does **not** imply unrestricted storage, full-text use, embedding, training, redistribution or public display rights.
- Keep bibliographic metadata separate from article full text. **Do not automatically download or vector-index copyrighted PDFs or abstracts.** No persistent RAG store is needed for this product.
- Inspect provider terms and item-level licenses; retain attribution, provenance and permitted-use metadata. Restrict cache/storage/redistribution by policy.
- Present versioned preprints and computed datasets with their scientific status and limitations; do not turn estimates into discoveries.
- Science Council is a research decision-support and evidence-tracing tool, not a substitute for domain expert review.

## Evaluation: Prove That Multi-Agent Collaboration Helps

Ship repeatable evaluations comparing **the complete Swarm system against one agent using the same MCP tools**, under stated cost and time budgets. Maintain two evaluation modes: reproducible fixture/snapshot-based runs and a live-API demonstration.

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
5. The **remote A2A Verifier**, in a separate process, independently re-fetches evidence and emits revision-bound verdicts.
6. The deterministic gate rejects stale / missing verification; Finalizer displays only supportable conclusions and explicit uncertainties.
7. The single conversation visibly differentiates **Swarm handoff, MCP call, and A2A verification**, with the final assessment at the top.

**Scientific guardrail:** A calculated material property is not proof of manufacturing feasibility, operational safety, cost competitiveness or market adoption.

## Architectural Boundaries

- **Not** a general clinical/biomedical research platform.
- **Not** a collection of one-API-per-agent wrappers or a fixed routing Graph disguised as a Swarm.
- **Not** a generic paper summarizer or another Travel RAG project with different documents.
- **Not** an excuse to add unused MCP servers, distributed systems or model providers.
- **Not** a sequence of MVPs; this README describes the **single complete target system**.

## Primary Technical References

- [Strands Swarm](https://strandsagents.com/docs/user-guide/sdk/multi-agent/swarm/)
- [Strands A2A](https://strandsagents.com/docs/user-guide/sdk/multi-agent/agent-to-agent/)
- [Strands Multi-Agent Patterns](https://strandsagents.com/docs/user-guide/sdk/multi-agent/multi-agent-patterns/)
- Official provider API documentation is linked in the MCP table above.
