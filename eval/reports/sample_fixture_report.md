# AxiomResearch fixture evaluation report

- Source: `fixtures` (no live APIs)
- Generated: `2026-11-03T00:00:00+00:00`
- LLM-as-judge: `False`
- Budgets identical across modes: `True`

## Shared budgets

```json
{
  "max_handoffs": 8,
  "max_iterations": 8,
  "execution_timeout_seconds": 180.0,
  "node_timeout_seconds": 45.0,
  "max_tokens_per_run": 100000,
  "max_cost_usd_per_run": 1.0,
  "mcp_servers": [
    "mcp-literature",
    "mcp-materials",
    "mcp-research-data"
  ]
}
```

## Mode suite pass/fail

- **one_agent_no_gate** (one agent + same MCP, no gate): passed=`False`
- **one_agent_gate** (one agent + same MCP + A2A gate): passed=`False`
- **swarm_gate** (Swarm + A2A gate): passed=`True`

## Metrics

| Metric | one_agent_no_gate (P/F/H/A) | one_agent_gate (P/F/H/A) | swarm_gate (P/F/H/A) |
| --- | --- | --- | --- |
| `citation_validity` | 2/1/0/6 | 3/0/0/6 | 3/0/0/6 |
| `claim_to_source` | 0/5/0/4 | 3/2/0/4 | 5/0/0/4 |
| `planted_error_detection` | 1/7/0/1 | 5/3/0/1 | 8/0/0/1 |
| `verification_coverage` | 0/3/0/6 | 3/0/0/6 | 3/0/0/6 |
| `handoff_usefulness` | 0/0/2/7 | 0/0/2/7 | 0/0/2/7 | — Qualitative — human rubric only; never LLM-as-judge.
| `redundant_tools` | 1/0/0/8 | 1/0/0/8 | 1/0/0/8 |
| `latency` | 0/1/0/8 | 1/0/0/8 | 1/0/0/8 | — Scored where gold expects bounded failure (e.g. delayed_a2a).
| `token_cost` | 0/0/0/9 | 0/0/0/9 | 0/0/0/9 | — Declared in the metric set; gold cases may omit checks until live runs record accounting (fixture cells show absent).
| `failure_behavior` | 1/2/0/6 | 3/0/0/6 | 3/0/0/6 |

P=pass F=fail H=pending_human A=absent (no gold check for that metric).

## Unbundling

- Gate credits (Verifier, not Swarm): **5**
- Swarm credits (collaboration, not Verifier): **2**

Fixture three-way report: swarm_gate passed=True; gate_credits=5; swarm_credits=2. Do not credit Swarm for Verifier gains (see gate_credits).

