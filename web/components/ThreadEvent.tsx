"use client";

import { ClaimExpand } from "@/components/ClaimExpand";
import type { ClaimView, ServerEvent } from "@/lib/types";

type Props = {
  event: ServerEvent;
  claim?: ClaimView;
};

function agentLabel(id: string | undefined): string {
  return (id || "agent").replace(/_/g, " ");
}

function toolSummaryText(summary: string | undefined, toolName: string | undefined): string {
  const raw = (summary || "").trim();
  if (!raw) {
    return toolName || "tool";
  }
  // Never dump tool JSON into the thread.
  if (raw.startsWith("{") || raw.startsWith("[")) {
    return toolName ? `${toolName} completed` : "Tool completed";
  }
  return raw.length > 180 ? `${raw.slice(0, 177)}…` : raw;
}

export function ThreadEvent({ event, claim }: Props) {
  if (event.type === "evidence.updated" && event.claim_id && claim) {
    return <ClaimExpand claim={claim} />;
  }

  if (event.type === "agent.handoff") {
    return (
      <div className="evt evt--swarm">
        <span className="evt__tag">Swarm handoff</span>
        <p>
          {agentLabel(event.from_agent)} → {agentLabel(event.to_agent)}
          {event.reason ? ` · ${event.reason}` : ""}
        </p>
      </div>
    );
  }

  if (event.type === "a2a.verification") {
    return (
      <div className="evt evt--a2a">
        <span className="evt__tag">Remote A2A</span>
        <p>
          Verification · {event.claim_id} · {event.status}
          {event.verified_revision != null ? ` · r${event.verified_revision}` : ""}
        </p>
      </div>
    );
  }

  if (event.type === "verification.gate") {
    return (
      <div className="evt evt--a2a">
        <span className="evt__tag">Remote A2A</span>
        <p>
          Gate {event.passed ? "passed" : "failed"}
          {event.detail ? ` · ${event.detail}` : ""}
        </p>
      </div>
    );
  }

  if (event.type === "tool.summary") {
    return (
      <div className="evt evt--tool">
        <span className="evt__tag">Tool</span>
        <p>
          {event.tool_name}
          {event.ok === false ? " · failed" : ""} ·{" "}
          {toolSummaryText(event.summary, event.tool_name)}
        </p>
      </div>
    );
  }

  if (event.type === "hypothesis.created") {
    return (
      <div className="evt evt--swarm">
        <span className="evt__tag">Hypothesis</span>
        <p>
          {event.hypothesis_id}
          {event.author_agent ? ` · ${agentLabel(event.author_agent)}` : ""}
        </p>
      </div>
    );
  }

  if (event.type === "agent.started") {
    return (
      <div className="evt evt--swarm">
        <span className="evt__tag">Swarm</span>
        <p>{agentLabel(event.agent_id)} started</p>
      </div>
    );
  }

  if (event.type === "run.failed") {
    return (
      <div className="evt evt--fail">
        <span className="evt__tag">Failed</span>
        <p>{event.reason || "Run failed"}</p>
      </div>
    );
  }

  if (event.type === "evidence.updated") {
    return (
      <div className="evt evt--swarm">
        <span className="evt__tag">Evidence</span>
        <p>
          {event.evidence_id || "updated"}
          {event.revision != null ? ` · r${event.revision}` : ""}
        </p>
      </div>
    );
  }

  return null;
}
