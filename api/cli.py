"""CLI: ``python -m api.cli "question"`` — Swarm node history + ledger summary."""

from __future__ import annotations

import argparse
import json
import sys

from api.swarm.runtime import run_research_swarm
from axiom_research.settings import require_gemini, settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run local AxiomResearch Swarm (no Finalizer)."
    )
    parser.add_argument("question", help="Research question")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use scripted mock models (no Gemini / no live MCP)",
    )
    args = parser.parse_args(argv)

    if args.mock:
        from api.swarm.scripted_model import ScriptedModel, handoff_turn, text_turn, tool_turn
        from axiom_research.identities import AgentId

        models = {
            AgentId.PLANNER: ScriptedModel(
                [handoff_turn("investigator", "Retrieve sources"), text_turn()]
            ),
            AgentId.INVESTIGATOR: ScriptedModel(
                [
                    tool_turn(
                        "upsert_source",
                        {
                            "payload": {
                                "source_id": "src-cli-1",
                                "identifier": "doi:10.example/cli",
                                "retrieved_at": "2026-11-02T00:00:00Z",
                                "provider": "crossref",
                                "fingerprint": "fp-src-cli",
                            }
                        },
                        tool_use_id="upsert-1",
                    ),
                    text_turn("sources recorded"),
                ]
            ),
            AgentId.DATA_ANALYST: ScriptedModel([text_turn()]),
            AgentId.CHALLENGER: ScriptedModel([text_turn()]),
        }
        result = run_research_swarm(args.question, models=models, mcp_tools=[])
    else:
        require_gemini(settings)
        # Live Gemini; MCP tools are attached by the WS/api path (Phase 4+).
        result = run_research_swarm(args.question, mcp_tools=[])

    print(f"status: {result.status}")
    if result.reason:
        print(f"reason: {result.reason}")
    print(f"node_history: {' → '.join(result.node_history) or '(empty)'}")
    print(f"execution_count: {result.execution_count}")
    print(f"tokens: {result.accounting.total_tokens}")
    print(f"cost_usd: {result.accounting.total_cost_usd:.6f}")
    print(f"ledger: {json.dumps(result.ledger_summary)}")
    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
