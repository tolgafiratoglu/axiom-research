"use client";

import { useState } from "react";

import type { FinalAssessment } from "@/lib/types";

type Props = {
  id: string;
  questionHint?: string | null;
  assessment: FinalAssessment;
};

export function AssessmentHistoryCard({ questionHint, assessment }: Props) {
  const [open, setOpen] = useState(false);
  const preview =
    assessment.conclusions.trim().split("\n")[0]?.slice(0, 120) ||
    "Previous assessment";

  return (
    <div className="hist">
      <button
        type="button"
        className="hist__toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="hist__tag">Prior assessment</span>
        <span className="hist__preview">
          {questionHint ? `${questionHint} · ` : ""}
          {preview}
          {assessment.conclusions.length > 120 ? "…" : ""}
        </span>
        <span className="hist__chevron">{open ? "Collapse" : "Expand"}</span>
      </button>
      {open ? (
        <div className="hist__body">
          <pre className="hist__conclusions">{assessment.conclusions}</pre>
          {assessment.citations.length > 0 ? (
            <p className="hist__meta">Citations: {assessment.citations.join(" · ")}</p>
          ) : null}
          {assessment.disputed.length > 0 ? (
            <ul className="hist__disputed">
              {assessment.disputed.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
          ) : null}
          {assessment.uncertainty ? (
            <p className="hist__meta">{assessment.uncertainty}</p>
          ) : null}
        </div>
      ) : null}

      <style jsx>{`
        .hist {
          border-left: 2px solid var(--line);
          padding-left: 0.65rem;
        }
        .hist__toggle {
          display: grid;
          grid-template-columns: auto 1fr auto;
          gap: 0.45rem;
          align-items: baseline;
          width: 100%;
          padding: 0;
          border: none;
          background: transparent;
          color: inherit;
          text-align: left;
          cursor: pointer;
        }
        .hist__tag {
          font-size: 0.68rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          font-weight: 650;
          color: var(--ink-muted);
        }
        .hist__preview {
          font-size: 0.88rem;
          color: var(--ink-muted);
          line-height: 1.35;
        }
        .hist__chevron {
          font-size: 0.72rem;
          color: var(--ink-muted);
        }
        .hist__body {
          margin-top: 0.45rem;
          padding-top: 0.35rem;
          border-top: 1px dashed var(--line);
        }
        .hist__conclusions {
          margin: 0;
          white-space: pre-wrap;
          font-family: inherit;
          font-size: 0.9rem;
          line-height: 1.45;
        }
        .hist__meta {
          margin: 0.4rem 0 0;
          font-size: 0.82rem;
          color: var(--ink-muted);
        }
        .hist__disputed {
          margin: 0.35rem 0 0;
          padding-left: 1.1rem;
          color: var(--warn);
          font-size: 0.82rem;
        }
      `}</style>
    </div>
  );
}
