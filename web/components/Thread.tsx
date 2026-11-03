"use client";

import { AssessmentHistoryCard } from "@/components/AssessmentHistoryCard";
import { ThreadEvent } from "@/components/ThreadEvent";
import type { ClaimView, ThreadItem } from "@/lib/types";

type Props = {
  items: ThreadItem[];
  claims: Record<string, ClaimView>;
};

export function Thread({ items, claims }: Props) {
  return (
    <section className="thread" aria-label="Investigation thread">
      {items.length === 0 ? (
        <p className="thread__empty">
          Investigation events appear here. Only this region scrolls.
        </p>
      ) : (
        <ul className="thread__list">
          {items.map((item) => {
            if (item.kind === "user") {
              return (
                <li key={item.id} className="thread__item thread__item--user">
                  <span className="thread__label">You</span>
                  <p>{item.text}</p>
                </li>
              );
            }
            if (item.kind === "assessment_pointer") {
              return (
                <li key={item.id} className="thread__item thread__item--pointer">
                  {item.text}
                </li>
              );
            }
            if (item.kind === "assessment_history") {
              return (
                <li key={item.id} className="thread__item">
                  <AssessmentHistoryCard
                    id={item.id}
                    questionHint={item.questionHint}
                    assessment={item.assessment}
                  />
                </li>
              );
            }
            const claimId = item.event.claim_id || undefined;
            return (
              <li key={item.id} className="thread__item">
                <ThreadEvent
                  event={item.event}
                  claim={claimId ? claims[claimId] : undefined}
                />
              </li>
            );
          })}
        </ul>
      )}

      <style jsx>{`
        .thread {
          flex: 1;
          overflow-y: auto;
          padding: 1rem 1.25rem 1.25rem;
          min-height: 0;
        }
        .thread__empty {
          margin: 1.5rem 0 0;
          color: var(--ink-muted);
          font-size: 0.95rem;
        }
        .thread__list {
          margin: 0;
          padding: 0;
          list-style: none;
          display: grid;
          gap: 0.75rem;
        }
        .thread__item {
          margin: 0;
        }
        .thread__item--user p {
          margin: 0.2rem 0 0;
          font-size: 0.95rem;
          line-height: 1.4;
        }
        .thread__label {
          font-size: 0.7rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--ink-muted);
        }
        .thread__item--pointer {
          color: var(--ink-muted);
          font-style: italic;
          font-size: 0.88rem;
          border-left: 2px solid var(--line);
          padding-left: 0.65rem;
        }
      `}</style>
    </section>
  );
}
