"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { AssessmentPanel } from "@/components/AssessmentPanel";
import { Composer } from "@/components/Composer";
import { Thread } from "@/components/Thread";
import { mergeClaimFromEvent } from "@/lib/claims";
import type {
  AgentId,
  ClaimView,
  FinalAssessment,
  RunPhase,
  ServerEvent,
  ThreadItem,
} from "@/lib/types";
import { SessionSocket } from "@/lib/ws";

function isServerEvent(value: ServerEvent): boolean {
  return typeof value?.type === "string" && typeof value?.event_id === "string";
}

function isLayoutDemo(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return new URLSearchParams(window.location.search).get("demo") === "layout";
}

/** Offline fixture for 6.9 browser layout check — no live API / Gemini. */
function layoutDemoSeed(): {
  phase: RunPhase;
  activeAgent: AgentId | null;
  claimIds: string[];
  assessment: FinalAssessment | null;
  items: ThreadItem[];
  claims: Record<string, ClaimView>;
} {
  return {
    phase: "running",
    activeAgent: "investigator",
    claimIds: ["claim-1"],
    assessment: null,
    items: [
      {
        kind: "assessment_history",
        id: "hist-demo",
        questionHint: "Prior solid-state question",
        assessment: {
          conclusions: "- Earlier run concluded evidence was incomplete.",
          citations: ["doi:10.example/prior"],
          disputed: ["[insufficient_evidence] Commercial readiness claim"],
          uncertainty:
            "Scientific guardrail: A calculated material property is not proof of manufacturing feasibility, operational safety, cost competitiveness or market adoption.",
        },
      },
      {
        kind: "user",
        id: "user-demo",
        text: "Can solid-state batteries replace conventional lithium-ion?",
      },
      {
        kind: "event",
        id: "evt-handoff",
        event: {
          type: "agent.handoff",
          event_id: "evt-handoff",
          ts: new Date().toISOString(),
          session_id: "demo",
          run_id: "run-demo",
          from_agent: "planner",
          to_agent: "investigator",
        },
      },
      {
        kind: "event",
        id: "evt-claim",
        event: {
          type: "evidence.updated",
          event_id: "evt-claim",
          ts: new Date().toISOString(),
          session_id: "demo",
          run_id: "run-demo",
          claim_id: "claim-1",
          revision: 1,
          statement: "Reported ionic conductivity is within a stated range.",
          source_refs: ["doi:10.example/1"],
          unit: "S/cm",
          verification_status: "pending",
        },
      },
      {
        kind: "event",
        id: "evt-a2a",
        event: {
          type: "a2a.verification",
          event_id: "evt-a2a",
          ts: new Date().toISOString(),
          session_id: "demo",
          run_id: "run-demo",
          verification_id: "ver-1",
          claim_id: "claim-1",
          status: "verified",
          verified_revision: 1,
        },
      },
    ],
    claims: {
      "claim-1": {
        claimId: "claim-1",
        statement: "Reported ionic conductivity is within a stated range.",
        sourceRefs: ["doi:10.example/1"],
        unit: "S/cm",
        verificationStatus: "verified",
        revision: 1,
      },
    },
  };
}

export function ResearchShell() {
  const socketRef = useRef<SessionSocket | null>(null);
  const [socketStatus, setSocketStatus] = useState("connecting");
  const [phase, setPhase] = useState<RunPhase>("idle");
  const [activeAgent, setActiveAgent] = useState<AgentId | null>(null);
  const [claimIds, setClaimIds] = useState<string[]>([]);
  const [failReason, setFailReason] = useState<string | null>(null);
  const [assessment, setAssessment] = useState<FinalAssessment | null>(null);
  const [liveRunId, setLiveRunId] = useState<string | null>(null);
  const [items, setItems] = useState<ThreadItem[]>([]);
  const [claims, setClaims] = useState<Record<string, ClaimView>>({});

  const claimCount = useMemo(() => new Set(claimIds).size, [claimIds]);

  useEffect(() => {
    if (isLayoutDemo()) {
      const demoSeed = layoutDemoSeed();
      setSocketStatus("open");
      setPhase(demoSeed.phase);
      setActiveAgent(demoSeed.activeAgent);
      setClaimIds(demoSeed.claimIds);
      setAssessment(demoSeed.assessment);
      setItems(demoSeed.items);
      setClaims(demoSeed.claims);
      return;
    }
    const socket = new SessionSocket({
      onStatus: setSocketStatus,
      onEvent: (event) => {
        if (!isServerEvent(event) || event.type === "heartbeat") {
          return;
        }
        handleEvent(event);
      },
    });
    socketRef.current = socket;
    socket.connect();
    return () => socket.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleEvent(event: ServerEvent) {
    setLiveRunId(event.run_id || null);
    setClaims((prev) => mergeClaimFromEvent(prev, event));

    if (event.type === "agent.started" && event.agent_id) {
      setPhase("running");
      setActiveAgent(event.agent_id);
    }
    if (event.type === "agent.handoff" && event.to_agent) {
      setPhase("running");
      setActiveAgent(event.to_agent);
    }
    if (event.type === "evidence.updated" && event.claim_id) {
      setClaimIds((prev) => [...prev, event.claim_id as string]);
    }
    if (event.type === "a2a.verification" && event.claim_id) {
      setClaimIds((prev) => [...prev, event.claim_id as string]);
    }
    if (event.type === "run.failed") {
      setPhase("failed");
      setFailReason(event.reason || "Run failed");
      setActiveAgent(null);
      // Never surface a draft conclusion on failure.
      setAssessment(null);
    }
    // 6.7: answer.final fills sticky once; thread gets one-line pointer only.
    if (event.type === "answer.final") {
      setPhase("complete");
      setActiveAgent(null);
      setAssessment({
        conclusions: event.conclusions || "",
        citations: event.citations || [],
        disputed: event.disputed || [],
        uncertainty: event.uncertainty ?? null,
      });
      setItems((prev) => [
        ...prev,
        {
          kind: "assessment_pointer",
          id: `ptr-${event.event_id}`,
          text: "Final assessment is above",
        },
      ]);
      return;
    }

    setItems((prev) => [
      ...prev,
      { kind: "event", id: event.event_id, event },
    ]);
  }

  function onAsk(question: string) {
    // 6.8: sticky → in-progress; prior assessment pinned as collapsed history card.
    const prior = assessment;
    const priorHint = [...items]
      .reverse()
      .find((item): item is Extract<ThreadItem, { kind: "user" }> => item.kind === "user")
      ?.text;

    setPhase("running");
    setActiveAgent(null);
    setClaimIds([]);
    setFailReason(null);
    setAssessment(null);

    setItems((prev) => {
      const next = [...prev];
      if (prior) {
        next.push({
          kind: "assessment_history",
          id: `hist-${Date.now()}`,
          questionHint: priorHint ? priorHint.slice(0, 80) : null,
          assessment: prior,
        });
      }
      next.push({ kind: "user", id: `user-${Date.now()}`, text: question });
      return next;
    });
    if (!isLayoutDemo()) {
      socketRef.current?.ask(question);
    }
  }

  function onCancel() {
    if (!isLayoutDemo()) {
      socketRef.current?.cancel(liveRunId);
    } else {
      setPhase("idle");
      setActiveAgent(null);
    }
  }

  return (
    <div className="shell">
      <div className="shell__frame">
        <AssessmentPanel
          brand="AxiomResearch"
          phase={phase}
          activeAgent={activeAgent}
          claimCount={claimCount}
          failReason={failReason}
          assessment={assessment}
          socketStatus={socketStatus}
        />
        <Thread items={items} claims={claims} />
        <Composer
          disabled={socketStatus !== "open"}
          running={phase === "running"}
          onAsk={onAsk}
          onCancel={onCancel}
        />
      </div>

      <style jsx>{`
        .shell {
          min-height: 100dvh;
          display: flex;
          justify-content: center;
          padding: 0.75rem;
        }
        .shell__frame {
          width: min(100%, var(--shell-max));
          min-height: calc(100dvh - 1.5rem);
          max-height: calc(100dvh - 1.5rem);
          display: flex;
          flex-direction: column;
          background: rgba(255, 255, 255, 0.35);
          border: 1px solid var(--line);
          border-radius: 0.5rem;
          overflow: hidden;
        }
        @media (max-width: 640px) {
          .shell {
            padding: 0;
          }
          .shell__frame {
            width: 100%;
            min-height: 100dvh;
            max-height: 100dvh;
            border-radius: 0;
            border-left: none;
            border-right: none;
          }
        }
      `}</style>
    </div>
  );
}
