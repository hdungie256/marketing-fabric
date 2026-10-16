"""Shared glossary note vocabulary (split from metric.py to avoid import cycles).

Glossary `notes` must use these keys so metric cards and the definition
dialog render them identically. Free-text cautions belong in `limitations`.
"""

NOTE_TEXT: dict[str, str] = {
    "currency_unverified": "Currency of monetary values is not stated in the source (R10).",
    "retrospective_target": "Retrospective synthetic target (R14).",
    "estimate_not_profit": "Estimate, not accounting profit.",
    "attributed_not_incremental": "Attributed, not incremental.",
    "first_in_observed_history": "First within observed history.",
}
FOOTNOTE_NOTES = {"currency_unverified"}
