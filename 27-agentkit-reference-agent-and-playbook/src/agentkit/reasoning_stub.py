"""STUB: a deterministic rule-based stand-in for a language model.

It drafts two things: the correction for a returned payment (S08) and the case note (S11). It is a set of
string templates plus a field lookup. It is NOT a model, it has no learned behavior, and nothing it writes
describes how a language model behaves. A real model would sit behind the same two methods; this repo does
not contain one and no API key is needed.

Every draft carries `stub=True` and the label below, so a reader of an audit trace cannot mistake it for
model output.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

STUB_LABEL = "STUB (deterministic template, not a language model)"


@dataclass(frozen=True)
class Draft:
    payment_id: str
    field: str
    old_value: str
    new_value: str
    message: str
    digest: str
    stub: bool = True
    label: str = STUB_LABEL


def correction_digest(payment_id: str, field: str, new_value: str) -> str:
    """A short fingerprint of a correction. An approval is only valid for the digest it was given for."""
    return hashlib.sha256(f"{payment_id}|{field}|{new_value}".encode("utf-8")).hexdigest()[:16]


class StubReasoner:
    is_model = False
    label = STUB_LABEL

    def draft_correction(self, *, case_id: str, reason_code: str, rule: dict, payment: dict, advised_value: str,
                         name_class: str, name_score: float) -> Draft:
        field = rule["field_to_correct"]
        old = payment.get(field, "")
        new = advised_value.strip()
        message = (f"[STUB] Correct {field} on {payment['payment_id']} from '{old}' to '{new}'. Return reason "
                   f"{reason_code}: {rule['description']}. Name match {name_class} ({name_score:.2f}). "
                   f"Resubmit only after four-eyes approval.")
        return Draft(payment["payment_id"], field, old, new, message,
                     correction_digest(payment["payment_id"], field, new))

    def draft_case_note(self, *, case_id: str, kind: str, reason_code: str, disposition: Optional[str],
                        name_class: Optional[str], hits: list, draft: Optional[Draft], gate: Optional[str],
                        reason: str = "") -> str:
        parts = [f"[STUB] Case {case_id}, reason {reason_code}."]
        if name_class:
            parts.append(f"Name match {name_class}.")
        if hits:
            parts.append("Watch-list hit: " + ", ".join(f"{h['party_id']} ({h['score']:.2f})" for h in hits) + ".")
        else:
            parts.append("No watch-list hit.")
        if draft is not None:
            parts.append(f"Proposed correction: {draft.field} {draft.old_value or '(blank)'} -> {draft.new_value}.")
        if kind == "handover":
            parts.append(f"Waiting for a person at {gate}." if gate else "Handed to a person.")
        else:
            parts.append(f"Disposition: {disposition}.")
        if reason:
            parts.append(reason)
        parts.append("Template text; no language model wrote this note.")
        return " ".join(parts)
