"use client";

import { FormEvent, useState } from "react";

type Props = {
  disabled: boolean;
  running: boolean;
  onAsk: (question: string) => void;
  onCancel: () => void;
};

export function Composer({ disabled, running, onAsk, onCancel }: Props) {
  const [value, setValue] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    const q = value.trim();
    if (!q || disabled || running) {
      return;
    }
    onAsk(q);
    setValue("");
  }

  return (
    <form className="composer" onSubmit={submit}>
      <label className="composer__label" htmlFor="axiom-ask">
        Question
      </label>
      <div className="composer__row">
        <textarea
          id="axiom-ask"
          rows={2}
          value={value}
          disabled={disabled || running}
          placeholder="Can solid-state batteries replace conventional lithium-ion?"
          onChange={(ev) => setValue(ev.target.value)}
          onKeyDown={(ev) => {
            if (ev.key === "Enter" && !ev.shiftKey) {
              ev.preventDefault();
              submit(ev);
            }
          }}
        />
        {running ? (
          <button type="button" className="composer__btn composer__btn--cancel" onClick={onCancel}>
            Cancel
          </button>
        ) : (
          <button type="submit" className="composer__btn" disabled={disabled || !value.trim()}>
            Ask
          </button>
        )}
      </div>

      <style jsx>{`
        .composer {
          flex-shrink: 0;
          padding: 0.85rem 1.25rem 1.1rem;
          border-top: 1px solid var(--line);
          background: rgba(248, 251, 249, 0.96);
        }
        .composer__label {
          display: block;
          margin-bottom: 0.35rem;
          font-size: 0.7rem;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: var(--ink-muted);
        }
        .composer__row {
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 0.6rem;
          align-items: end;
        }
        textarea {
          width: 100%;
          resize: vertical;
          min-height: 3.2rem;
          max-height: 8rem;
          padding: 0.65rem 0.75rem;
          border: 1px solid var(--line);
          border-radius: 0.35rem;
          background: #fff;
          color: var(--ink);
        }
        textarea:focus {
          outline: 2px solid var(--accent-soft);
          border-color: var(--accent);
        }
        .composer__btn {
          min-height: 2.75rem;
          padding: 0 1rem;
          border: none;
          border-radius: 0.35rem;
          background: var(--accent);
          color: #f4fbf8;
          font-weight: 600;
          cursor: pointer;
        }
        .composer__btn:disabled {
          opacity: 0.45;
          cursor: not-allowed;
        }
        .composer__btn--cancel {
          background: var(--fail);
        }
      `}</style>
    </form>
  );
}
