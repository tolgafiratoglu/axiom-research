/** Stable UI event types mirrored from axiom_research.events (Phase 0.5). */

export type AgentId =
  | "planner"
  | "investigator"
  | "data_analyst"
  | "challenger"
  | "verifier"
  | "finalizer";

export type ServerEventType =
  | "agent.started"
  | "agent.handoff"
  | "tool.summary"
  | "evidence.updated"
  | "hypothesis.created"
  | "a2a.verification"
  | "verification.gate"
  | "answer.final"
  | "run.failed"
  | "heartbeat";

export type ServerEvent = {
  type: ServerEventType;
  event_id: string;
  ts: string;
  session_id: string;
  run_id: string;
  agent_id?: AgentId;
  from_agent?: AgentId;
  to_agent?: AgentId;
  reason?: string | null;
  tool_name?: string;
  summary?: string;
  ok?: boolean;
  evidence_id?: string | null;
  claim_id?: string | null;
  revision?: number | null;
  statement?: string | null;
  source_refs?: string[];
  unit?: string | null;
  value?: number | string | null;
  method?: string | null;
  license?: string | null;
  evidence_kind?: string | null;
  verification_status?: string | null;
  retrieved_at?: string | null;
  hypothesis_id?: string;
  author_agent?: AgentId;
  verification_id?: string;
  status?: string;
  verified_revision?: number | null;
  passed?: boolean;
  detail?: string | null;
  conclusions?: string;
  citations?: string[];
  disputed?: string[];
  uncertainty?: string | null;
  last_event_id?: string | null;
};

export type FinalAssessment = {
  conclusions: string;
  citations: string[];
  disputed: string[];
  uncertainty: string | null;
};

export type RunPhase = "idle" | "running" | "complete" | "failed";

export type ThreadItem =
  | { kind: "user"; id: string; text: string }
  | { kind: "event"; id: string; event: ServerEvent }
  | { kind: "assessment_pointer"; id: string; text: string }
  | {
      kind: "assessment_history";
      id: string;
      questionHint?: string | null;
      assessment: FinalAssessment;
    };

/** Merge later evidence/verification updates onto the same claim id for expand. */
export type ClaimView = {
  claimId: string;
  statement?: string | null;
  sourceRefs: string[];
  unit?: string | null;
  value?: number | string | null;
  method?: string | null;
  license?: string | null;
  evidenceKind?: string | null;
  verificationStatus?: string | null;
  retrievedAt?: string | null;
  revision?: number | null;
  evidenceId?: string | null;
};
