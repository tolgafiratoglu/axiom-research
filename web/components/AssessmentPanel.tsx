"use client";

import type { AgentId, FinalAssessment, RunPhase } from "@/lib/types";

type Props = {
  brand: string;
  phase: RunPhase;
  activeAgent: AgentId | null;
  claimCount: number;
  failReason: string | null;
  assessment: FinalAssessment | null;
  socketStatus: string;
};

function phaseLabel(phase: RunPhase): string {
  switch (phase) {
    case "idle":
      return "Ready";
    case "running":
      return "Investigating";
    case "complete":
      return "Assessment ready";
    case "failed":
      return "Run incomplete";
  }
}

export function AssessmentPanel({
  brand,
  phase,
  activeAgent,
  claimCount,
  failReason,
  assessment,
  socketStatus,
}: Props) {
  const running = phase === "running";
  const showFinal = phase === "complete" && assessment !== null;

  return (
    <header className="assessment" aria-live="polite">
      <div className="assessment__brand-row">
        <p className="assessment__brand">{brand}</p>
        <p className="assessment__socket" data-status={socketStatus}>
          {socketStatus}
        </p>
      </div>
      <h1 className="assessment__title">Final Assessment</h1>

      {running || phase === "idle" ? (
        <div className="assessment__status">
          <p className="assessment__phase">{phaseLabel(phase)}</p>
          {running ? (
            <ul className="assessment__meta">
              <li>
                Active agent:{" "}
                <strong>{activeAgent ? activeAgent.replace(/_/g, " ") : "—"}</strong>
              </li>
              <li>
                Claims seen: <strong>{claimCount}</strong>
              </li>
            </ul>
          ) : (
            <p className="assessment__hint">
              Ask a materials or energy-storage question. Status stays here while
              the run is live — never a draft conclusion.
            </p>
          )}
        </div>
      ) : null}

      {phase === "failed" ? (
        <div className="assessment__status assessment__status--fail">
          <p className="assessment__phase">{phaseLabel(phase)}</p>
          <p className="assessment__fail">{failReason || "Verification or run failed."}</p>
        </div>
      ) : null}

      {showFinal ? (
        <div className="assessment__final">
          <p className="assessment__phase">{phaseLabel(phase)}</p>
          <div className="assessment__conclusions">{assessment.conclusions}</div>
          {assessment.citations.length > 0 ? (
            <p className="assessment__citations">
              Citations: {assessment.citations.join(" · ")}
            </p>
          ) : null}
          {assessment.disputed.length > 0 ? (
            <ul className="assessment__disputed">
              {assessment.disputed.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
          {assessment.uncertainty ? (
            <p className="assessment__uncertainty">{assessment.uncertainty}</p>
          ) : null}
        </div>
      ) : null}

      <style jsx>{`
        .assessment {
          position: sticky;
          top: 0;
          z-index: 20;
          padding: 1.1rem 1.25rem 1rem;
          background: var(--panel);
          backdrop-filter: blur(10px);
          border-bottom: 1px solid var(--line);
        }
        .assessment__brand-row {
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          gap: 0.75rem;
        }
        .assessment__brand {
          margin: 0;
          font-family: var(--font-display);
          font-size: clamp(1.55rem, 3.2vw, 2rem);
          font-weight: 650;
          letter-spacing: -0.02em;
          line-height: 1.1;
        }
        .assessment__socket {
          margin: 0;
          font-size: 0.72rem;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: var(--ink-muted);
        }
        .assessment__socket[data-status="open"] {
          color: var(--accent);
        }
        .assessment__socket[data-status="error"],
        .assessment__socket[data-status="closed"] {
          color: var(--fail);
        }
        .assessment__title {
          margin: 0.35rem 0 0.65rem;
          font-family: var(--font-body);
          font-size: 0.78rem;
          font-weight: 600;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: var(--ink-muted);
        }
        .assessment__phase {
          margin: 0 0 0.4rem;
          font-size: 1.05rem;
          font-weight: 600;
        }
        .assessment__hint,
        .assessment__fail,
        .assessment__citations,
        .assessment__uncertainty {
          margin: 0;
          color: var(--ink-muted);
          font-size: 0.92rem;
          line-height: 1.45;
        }
        .assessment__meta {
          margin: 0;
          padding: 0;
          list-style: none;
          display: grid;
          gap: 0.25rem;
          font-size: 0.92rem;
          color: var(--ink-muted);
        }
        .assessment__status--fail .assessment__fail {
          color: var(--fail);
        }
        .assessment__conclusions {
          white-space: pre-wrap;
          font-size: 1rem;
          line-height: 1.5;
          margin: 0.25rem 0 0.65rem;
        }
        .assessment__disputed {
          margin: 0.4rem 0;
          padding-left: 1.1rem;
          color: var(--warn);
          font-size: 0.9rem;
        }
        .assessment__uncertainty {
          border-top: 1px solid var(--line);
          padding-top: 0.55rem;
          margin-top: 0.55rem;
        }
      `}</style>
    </header>
  );
}
