# AxiomResearch — canonical live demo

Operator walkthrough for the interview gold path. No tribal knowledge required.
**Agents / CI do not run this document** — it hits Compose, Gemini, and scientific APIs.

Pinned identifiers: [`demo/canonical_pins.json`](./demo/canonical_pins.json)  
Bring-up defaults: [`ReadMe.md`](./ReadMe.md) § Local Compose bring-up · [`.env.example`](./.env.example)

**Canonical question**

> Can solid-state batteries realistically replace conventional lithium-ion batteries? What do published studies, computed materials data, and deposited research datasets actually support?

---

## 0. Once per machine

```bash
cp .env.example .env          # set GEMINI_MODEL to a live Flash ID
mkdir -p ~/.config/rag
# ~/.config/rag/.env (chmod 600):
#   GEMINI_API_KEY=…
#   MP_API_KEY=…               # Materials Project — required for mp-19017
```

Optional host tools: `.venv` + `pip install -e ".[dev]"` (live smoke / pytest).

---

## 1. Compose up (full stack)

One command brings **web**, **api** (Swarm + gate + Finalizer), **verifier**, three MCP servers, and **postgres**:

```bash
docker compose config
docker compose up -d --build
```

`api` sets `AXIOM_LIVE_BOOTSTRAP=1` so the first `ask` loads MCP tools and the A2A Verifier client. Secrets stay on the host mount (`~/.config/rag` → `/config/rag`).

Health (expect HTTP 200):

```bash
curl -sf http://127.0.0.1:8210/health
curl -sf http://127.0.0.1:8211/health
curl -sf http://127.0.0.1:8212/health
curl -sf http://127.0.0.1:8201/.well-known/agent-card.json
curl -sf http://127.0.0.1:8200/health/live
curl -sf http://127.0.0.1:8200/health/ready
curl -sf http://127.0.0.1:3200/ >/dev/null
```

Optional pin smoke (live providers, not CI):

```bash
.venv/bin/python scripts/mcp_live_smoke.py
```

| Pin | Value | MCP |
| --- | --- | --- |
| Literature DOI / OpenAlex | `10.1038/nmat2440` (`doi:10.1038/nmat2440`) | `mcp-literature` |
| Materials Project | `mp-19017` (LiFePO4, **computed**) | `mcp-materials` |
| PubChem | CID `66377` (Li₂S) | `mcp-materials` |
| Zenodo record | `3233912` / `10.5281/zenodo.3233912` | `mcp-research-data` |
| DataCite PID | same DOI `10.5281/zenodo.3233912` | `mcp-research-data` (Verifier path) |

**Host-only fallback** (if you prefer not to build web/api images): keep Compose MCP + verifier + postgres, then:

```bash
export AXIOM_LIVE_BOOTSTRAP=1
export DATABASE_URL=postgresql://axiom:axiom@127.0.0.1:5434/axiom_research
export MCP_LITERATURE_URL=http://127.0.0.1:8210
export MCP_MATERIALS_URL=http://127.0.0.1:8211
export MCP_RESEARCH_DATA_URL=http://127.0.0.1:8212
export VERIFIER_URL=http://127.0.0.1:8201
export SECRETS_ENV_PATH=~/.config/rag/.env
.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8200
# other terminal: cd web && npm run dev
```

---

## 2. Open the UI

- Live demo: `http://127.0.0.1:3200/`
- Layout-only (no Gemini / no MCP): `http://127.0.0.1:3200/?demo=layout`

WebSocket: `ws://127.0.0.1:8200/ws/session` (`NEXT_PUBLIC_WS_URL`).

---

## 3. Ask the canonical question

1. Open `http://127.0.0.1:3200/` (not `?demo=layout`).
2. Paste the canonical question into the input and send (`ask` on the single WebSocket).
3. Sticky panel stays **in-progress** (status / active agent / claim counts) — **no draft conclusion**.

WS envelope (if you drive a client instead of the UI):

```json
{
  "type": "ask",
  "question": "Can solid-state batteries realistically replace conventional lithium-ion batteries? What do published studies, computed materials data, and deposited research datasets actually support?"
}
```

Cancel (optional): `{"type":"cancel","run_id":"<run_id>"}`.

---

## 4. What to point at in the interview

Watch the **investigation thread** (only this region scrolls). Call out four distinct signals:

### A. Swarm handoff — `agent.handoff`

- Planner → Investigator (or later Investigator ↔ Analyst ↔ Challenger).
- Visually distinct from tool rows and from A2A.
- A useful handoff changes the next task or the ledger — not a no-op hop.

### B. MCP retrieval — `tool.summary` / `evidence.updated`

- Investigator tools against **all three** MCP servers (literature, materials, research-data).
- Expand a claim inline: DOI / MP id / PubChem CID / Zenodo or DataCite PID, units, method, license, verification status.
- Expect pins such as `doi:10.1038/nmat2440`, `materials-project:mp-19017`, `pubchem:cid:66377`, `zenodo:3233912`.
- Group noisy tools; never show raw tool JSON or private chain-of-thought.

### C. Remote A2A verification — `a2a.verification` then `verification.gate`

- After Swarm stop, the **Verifier container** re-checks claims with its **own** MCP clients (fresh context — not a Swarm node).
- Dataset PID dual path is **enforced in tool allowlists**: Investigator has `zenodo_*` only; Verifier has `datacite_resolve_doi` only — same pin `10.5281/zenodo.3233912`, different fetch (9.3).
- Gate is deterministic application code; a successful A2A transport ≠ scientific truth.

### D. Sticky Final Assessment — `answer.final`

- Appears **once** in the sticky chrome when the gate passes.
- Thread gets only a short system line pointing upward — no duplicate assistant bubble.
- Conclusions must stay source-grounded. Sticky **uncertainty** always includes the scientific guardrail: *A calculated material property is not proof of manufacturing feasibility, operational safety, cost competitiveness or market adoption.*
- On follow-up, sticky returns to in-progress; prior assessment collapses into a history card in the thread.

Failure path (also fine to show): MCP 429/timeout → `tool.summary` with `ok=false`; unreachable Verifier → `run.failed` / gate fail — **no falsely confident** `answer.final`.

---

## 5. Done checklist

- [ ] `docker compose up -d --build` healthy (MCP, Verifier, api, web, Postgres)  
- [ ] Canonical question asked over one WebSocket  
- [ ] Pointed at **handoff**, **MCP**, **A2A**, **sticky assessment**  
- [ ] Guardrail visible in Final Assessment uncertainty (manufacturing / safety / cost / adoption)  

Tear down: `docker compose down` (add `-v` only to wipe Postgres).
