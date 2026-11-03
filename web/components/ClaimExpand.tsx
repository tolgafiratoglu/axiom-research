"use client";

import { useState } from "react";

import type { ClaimView } from "@/lib/types";

type Props = {
  claim: ClaimView;
};

function row(label: string, value: string | null | undefined) {
  if (!value) {
    return null;
  }
  return (
    <div className="claim__row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export function ClaimExpand({ claim }: Props) {
  const [open, setOpen] = useState(false);
  const title =
    claim.statement?.trim() ||
    `Claim ${claim.claimId}${claim.revision != null ? ` · r${claim.revision}` : ""}`;

  return (
    <div className="claim">
      <button
        type="button"
        className="claim__toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="claim__kind">Claim</span>
        <span className="claim__title">{title}</span>
        <span className="claim__chevron">{open ? "Collapse" : "Expand"}</span>
      </button>
      {open ? (
        <dl className="claim__details">
          {row("ID", claim.claimId)}
          {row(
            "Identifiers",
            claim.sourceRefs.length ? claim.sourceRefs.join(" · ") : null
          )}
          {row(
            "Value",
            claim.value != null
              ? `${claim.value}${claim.unit ? ` ${claim.unit}` : ""}`
              : claim.unit
                ? `unit ${claim.unit}`
                : null
          )}
          {row("Kind", claim.evidenceKind)}
          {row("Method", claim.method)}
          {row("License", claim.license)}
          {row("Retrieved", claim.retrievedAt)}
          {row("Revision", claim.revision != null ? String(claim.revision) : null)}
          {row("Verification", claim.verificationStatus || "pending")}
          {claim.evidenceId ? row("Evidence", claim.evidenceId) : null}
        </dl>
      ) : null}

      <style jsx>{`
        .claim {
          border-left: 2px solid var(--accent);
          padding-left: 0.65rem;
        }
        .claim__toggle {
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
        .claim__kind {
          font-size: 0.68rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--accent);
          font-weight: 650;
        }
        .claim__title {
          font-size: 0.92rem;
          line-height: 1.35;
        }
        .claim__chevron {
          font-size: 0.72rem;
          color: var(--ink-muted);
        }
        .claim__details {
          margin: 0.45rem 0 0;
          display: grid;
          gap: 0.28rem;
        }
        .claim__row {
          display: grid;
          grid-template-columns: 6.5rem 1fr;
          gap: 0.4rem;
          font-size: 0.82rem;
        }
        .claim__row dt {
          margin: 0;
          color: var(--ink-muted);
        }
        .claim__row dd {
          margin: 0;
          word-break: break-word;
        }
      `}</style>
    </div>
  );
}
