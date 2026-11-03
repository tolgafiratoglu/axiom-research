import type { ClaimView, ServerEvent } from "./types";

export function mergeClaimFromEvent(
  claims: Record<string, ClaimView>,
  event: ServerEvent
): Record<string, ClaimView> {
  if (event.type === "evidence.updated" && event.claim_id) {
    const id = event.claim_id;
    const prev = claims[id];
    return {
      ...claims,
      [id]: {
        claimId: id,
        statement: event.statement ?? prev?.statement,
        sourceRefs:
          event.source_refs && event.source_refs.length > 0
            ? event.source_refs
            : prev?.sourceRefs || [],
        unit: event.unit ?? prev?.unit,
        value: event.value ?? prev?.value,
        method: event.method ?? prev?.method,
        license: event.license ?? prev?.license,
        evidenceKind: event.evidence_kind ?? prev?.evidenceKind,
        verificationStatus:
          event.verification_status ?? prev?.verificationStatus ?? "pending",
        retrievedAt: event.retrieved_at ?? prev?.retrievedAt,
        revision: event.revision ?? prev?.revision,
        evidenceId: event.evidence_id ?? prev?.evidenceId,
      },
    };
  }

  if (event.type === "a2a.verification" && event.claim_id) {
    const id = event.claim_id;
    const prev = claims[id] || { claimId: id, sourceRefs: [] };
    return {
      ...claims,
      [id]: {
        ...prev,
        verificationStatus: event.status || prev.verificationStatus,
        revision: event.verified_revision ?? prev.revision,
      },
    };
  }

  return claims;
}
