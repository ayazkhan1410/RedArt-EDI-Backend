"""
ANSI X12 segment parse helpers (837P outbound reference + 999 inbound import).

Splits interchange text into segment dicts, then maps 999 AK/IK elements
into acknowledgement fields for persistence.
"""

from __future__ import annotations

from apps.edi.choices import AcknowledgementStatus, AcknowledgementType


def split_x12_segments(raw: str) -> list[str]:
    """Normalize raw X12 and return segment strings without trailing ~."""
    if raw is None:
        return []
    text = str(raw).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    # Allow either one-segment-per-line or continuous ~ stream.
    if "\n" in text and "~" in text:
        parts = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.endswith("~"):
                line = line[:-1]
            parts.append(line)
        return parts
    if "~" in text:
        return [p.strip() for p in text.split("~") if p.strip()]
    return [text]


def parse_segment(segment: str, *, element_separator: str = "*") -> dict:
    """
    Parse one segment into a dict.
    Example: AK2*837*0001*005010X222A1
      → {"id": "AK2", "elements": ["837", "0001", "005010X222A1"], "raw": "..."}
    """
    segment = (segment or "").strip()
    if segment.endswith("~"):
        segment = segment[:-1]
    parts = segment.split(element_separator)
    seg_id = (parts[0] or "").strip().upper()
    elements = parts[1:]
    return {
        "id": seg_id,
        "elements": elements,
        "raw": segment + "~",
    }


def parse_x12(raw: str, *, element_separator: str = "*") -> list[dict]:
    """Parse full X12 body into ordered list of segment dicts."""
    return [
        parse_segment(seg, element_separator=element_separator)
        for seg in split_x12_segments(raw)
    ]


def segments_by_id(segments: list[dict]) -> dict[str, list[dict]]:
    """Group segment dicts by segment id (preserves encounter order in lists)."""
    grouped: dict[str, list[dict]] = {}
    for seg in segments:
        grouped.setdefault(seg["id"], []).append(seg)
    return grouped


def _el(seg: dict | None, index: int, default=None):
    """1-based element index within segment (AK201 → index 1)."""
    if not seg:
        return default
    elements = seg.get("elements") or []
    i = index - 1
    if i < 0 or i >= len(elements):
        return default
    value = elements[i]
    return default if value in (None, "") else value


def map_999_ack_code(code) -> str:
    """Map IK501 / AK901 to AcknowledgementStatus."""
    code = (str(code or "").strip().upper() or "A")
    mapping = {
        "A": AcknowledgementStatus.ACCEPTED,
        "E": AcknowledgementStatus.ERROR,
        "R": AcknowledgementStatus.REJECTED,
        "P": AcknowledgementStatus.PARTIAL,
        "M": AcknowledgementStatus.REJECTED,
        "W": AcknowledgementStatus.PARTIAL,
        "X": AcknowledgementStatus.REJECTED,
    }
    return mapping.get(code, AcknowledgementStatus.ERROR)


def parse_999(raw: str) -> dict:
    """
    Parse a 999 Implementation Acknowledgment into structured fields + segments.

    Returns:
      {
        "segments": [...],
        "by_id": {...},
        "ack_type": "999",
        "status": "ACCEPTED",
        "affected_st02": "0001",
        "gs06": "1",
        "ik5_code": "A",
        "ak9_code": "A",
        "message": "...",
        "isa13": "...",
        "gs08": "005010X231A1",
      }
    """
    segments = parse_x12(raw)
    if not segments:
        raise ValueError("Empty X12 content.")

    by_id = segments_by_id(segments)
    st = (by_id.get("ST") or [None])[0]
    if st and _el(st, 1) != "999":
        raise ValueError(f"Expected ST*999, got ST*{_el(st, 1)}.")

    ak1 = (by_id.get("AK1") or [None])[0]
    ak2 = (by_id.get("AK2") or [None])[0]
    ik5 = (by_id.get("IK5") or [None])[0]
    ak9 = (by_id.get("AK9") or [None])[0]
    isa = (by_id.get("ISA") or [None])[0]
    gs = (by_id.get("GS") or [None])[0]

    ik5_code = _el(ik5, 1)
    ak9_code = _el(ak9, 1)
    # Prefer transaction-set result (IK5); fall back to functional group (AK9).
    status = map_999_ack_code(ik5_code or ak9_code)

    st02 = _el(ak2, 2)
    if st02 and str(st02).isdigit():
        st02 = str(st02).zfill(4) if len(str(st02)) <= 4 else str(st02)

    message_parts = []
    if ik5_code:
        message_parts.append(f"IK5={ik5_code}")
    if ak9_code:
        message_parts.append(f"AK9={ak9_code}")
    if _el(ak1, 1) or _el(ak1, 2):
        message_parts.append(f"AK1={_el(ak1, 1)}/{_el(ak1, 2)}")
    if _el(ak2, 1) or _el(ak2, 2):
        message_parts.append(f"AK2={_el(ak2, 1)}/{_el(ak2, 2)}")

    return {
        "segments": segments,
        "by_id": {k: v for k, v in by_id.items()},
        "ack_type": AcknowledgementType.X999,
        "status": status,
        "affected_st02": st02,
        "gs06": _el(ak1, 2) or _el(gs, 6),
        "ik5_code": ik5_code,
        "ak9_code": ak9_code,
        "ak1": {
            "functional_id": _el(ak1, 1),
            "group_control": _el(ak1, 2),
            "version": _el(ak1, 3),
        },
        "ak2": {
            "transaction_set": _el(ak2, 1),
            "st02": st02,
            "version": _el(ak2, 3),
        },
        "message": "; ".join(message_parts) or None,
        "isa13": _el(isa, 13),
        "gs08": _el(gs, 8),
    }


# CLP02 → claim outcome (HIPAA 835).
_CLP_PAID_CODES = frozenset({"1", "2", "3", "19", "20", "21"})
_CLP_DENIED_CODES = frozenset({"4"})
_CLP_REVIEW_CODES = frozenset({"22", "23", "25"})


def map_835_clp_outcome(clp02: str, payment_amount) -> str:
    """
    Map CLP02 (+ payment amount) to RemittanceClaimOutcome.
    Paid only when status is a processed-as-* code and payment > 0.
    """
    from decimal import Decimal

    from apps.edi.choices import RemittanceClaimOutcome

    code = str(clp02 or "").strip()
    try:
        amount = Decimal(str(payment_amount if payment_amount is not None else "0"))
    except Exception:
        amount = Decimal("0")

    if code in _CLP_DENIED_CODES:
        return RemittanceClaimOutcome.DENIED
    if code in _CLP_PAID_CODES:
        if amount > 0:
            return RemittanceClaimOutcome.PAID
        # Processed but $0 — treat as denial-like for Medicaid ERA simplicity.
        return RemittanceClaimOutcome.DENIED
    if code in _CLP_REVIEW_CODES:
        return RemittanceClaimOutcome.UNDER_REVIEW
    return RemittanceClaimOutcome.IGNORED


def _parse_decimal(value):
    from decimal import Decimal, InvalidOperation

    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def _parse_ccyymmdd(value):
    from datetime import datetime

    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        try:
            return datetime.strptime(text, "%Y%m%d").date()
        except ValueError:
            return None
    return None


def parse_835(raw: str) -> dict:
    """
    Parse a minimal 835 ERA into header fields + CLP claim lines.

    Returns:
      {
        "isa13", "gs06", "st02", "trace_number", "payment_method",
        "total_payment", "payment_date", "message", "claims": [
          {
            "claim_number", "clp_status_code", "outcome",
            "charge_amount", "payment_amount", "patient_responsibility",
            "payer_claim_control", "adjustment_codes",
          },
          ...
        ],
        "segments", "by_id",
      }
    """
    segments = parse_x12(raw)
    if not segments:
        raise ValueError("Empty X12 content.")

    by_id = segments_by_id(segments)
    st = (by_id.get("ST") or [None])[0]
    st01 = _el(st, 1)
    if st01 and st01 != "835":
        raise ValueError(f"Expected ST*835, got ST*{st01}.")
    if not st01:
        # Some pasted snippets omit ISA/GS/ST — require at least one CLP.
        if not by_id.get("CLP"):
            raise ValueError("Expected ST*835 or at least one CLP segment.")

    isa = (by_id.get("ISA") or [None])[0]
    gs = (by_id.get("GS") or [None])[0]
    bpr = (by_id.get("BPR") or [None])[0]
    trn = (by_id.get("TRN") or [None])[0]

    payment_date = None
    for dtm in by_id.get("DTM") or []:
        # DTM*405 / DTM*472 commonly used; prefer 405 (production date) then any.
        qualifier = str(_el(dtm, 1) or "")
        parsed = _parse_ccyymmdd(_el(dtm, 2))
        if parsed and qualifier in ("405", "472", "050"):
            payment_date = parsed
            break
        if parsed and payment_date is None:
            payment_date = parsed

    claims = []
    current = None
    cas_bits: list[str] = []

    def _flush():
        nonlocal current, cas_bits
        if current is None:
            return
        if cas_bits:
            current["adjustment_codes"] = ";".join(cas_bits)[:500]
        claims.append(current)
        current = None
        cas_bits = []

    for seg in segments:
        sid = seg.get("id")
        if sid == "CLP":
            _flush()
            claim_number = str(_el(seg, 1) or "").strip()
            clp02 = str(_el(seg, 2) or "").strip()
            charge = _parse_decimal(_el(seg, 3))
            payment = _parse_decimal(_el(seg, 4))
            patient_resp = _parse_decimal(_el(seg, 5))
            if not claim_number:
                continue
            current = {
                "claim_number": claim_number,
                "clp_status_code": clp02 or "",
                "outcome": map_835_clp_outcome(clp02, payment),
                "charge_amount": charge,
                "payment_amount": payment,
                "patient_responsibility": patient_resp,
                "payer_claim_control": (_el(seg, 7) or None),
                "adjustment_codes": None,
            }
            cas_bits = []
        elif sid == "CAS" and current is not None:
            # CAS*CO*45*10.00*1*...
            group = _el(seg, 1)
            reason = _el(seg, 2)
            amt = _el(seg, 3)
            if group or reason:
                cas_bits.append(f"{group or ''}:{reason or ''}:{amt or ''}")

    _flush()

    if not claims:
        raise ValueError("No CLP claim lines found in 835 content.")

    message_parts = []
    if _el(bpr, 1):
        message_parts.append(f"BPR01={_el(bpr, 1)}")
    if _el(trn, 2):
        message_parts.append(f"TRN02={_el(trn, 2)}")
    message_parts.append(f"CLP_COUNT={len(claims)}")

    return {
        "segments": segments,
        "by_id": {k: v for k, v in by_id.items()},
        "isa13": _el(isa, 13),
        "gs06": _el(gs, 6),
        "st02": _el(st, 2),
        "trace_number": _el(trn, 2),
        "payment_method": _el(bpr, 4),
        "total_payment": _parse_decimal(_el(bpr, 2)),
        "payment_date": payment_date,
        "message": "; ".join(message_parts) or None,
        "claims": claims,
        "transaction_type": "835",
    }


_277_DENIED_PREFIXES = frozenset({"A3", "A4", "A7", "A8", "R"})
_277_ACCEPTED_PREFIXES = frozenset({"A2", "A1", "A0"})


def map_277_stc_to_outcome(stc01: str) -> str:
    """Map STC01 health care claim status category → claim outcome label."""
    from apps.claim.choices import ClaimStatus

    prefix = str(stc01 or "").strip().upper().split(":")[0]
    if prefix in _277_DENIED_PREFIXES:
        return ClaimStatus.DENIED
    if prefix in _277_ACCEPTED_PREFIXES:
        return ClaimStatus.UNDER_REVIEW
    return ClaimStatus.UNDER_REVIEW


def map_277_aggregate_status(lines: list[dict]) -> str:
    """Aggregate line outcomes into AcknowledgementStatus."""
    if not lines:
        return AcknowledgementStatus.ERROR
    from apps.claim.choices import ClaimStatus

    outcomes = {line.get("outcome") for line in lines}
    if outcomes == {ClaimStatus.DENIED}:
        return AcknowledgementStatus.REJECTED
    if ClaimStatus.DENIED in outcomes:
        return AcknowledgementStatus.PARTIAL
    if ClaimStatus.UNDER_REVIEW in outcomes:
        return AcknowledgementStatus.ACCEPTED
    return AcknowledgementStatus.ACCEPTED


def parse_277(raw: str) -> dict:
    """
    Parse HIPAA 277 / 277CA claim status response (minimal CLP/TRN/REF/STC walk).
    """
    segments = parse_x12(raw)
    if not segments:
        raise ValueError("Empty X12 content.")

    by_id = segments_by_id(segments)
    st = (by_id.get("ST") or [None])[0]
    st01 = _el(st, 1)
    if st01 and st01 != "277":
        raise ValueError(f"Expected ST*277, got ST*{st01}.")

    isa = (by_id.get("ISA") or [None])[0]
    gs = (by_id.get("GS") or [None])[0]

    claim_lines = []
    current_claim_number = None
    current_tracking = None

    for seg in segments:
        sid = seg.get("id")
        if sid == "TRN":
            trn01 = _el(seg, 1)
            if trn01 == "2":
                current_tracking = _el(seg, 2)
                current_claim_number = None
        elif sid == "REF":
            qualifier = str(_el(seg, 1) or "").upper()
            if qualifier in ("1K", "D9", "EA", "F8"):
                current_claim_number = str(_el(seg, 2) or "").strip() or current_claim_number
        elif sid == "STC":
            stc01 = str(_el(seg, 1) or "")
            outcome = map_277_stc_to_outcome(stc01)
            claim_number = current_claim_number or current_tracking
            if not claim_number:
                continue
            claim_lines.append(
                {
                    "claim_number": claim_number,
                    "tracking_number": current_tracking,
                    "stc_code": stc01,
                    "outcome": outcome,
                }
            )

    if not claim_lines:
        raise ValueError("No TRN/STC claim status lines found in 277 content.")

    message_parts = [f"STC_COUNT={len(claim_lines)}"]
    agg = map_277_aggregate_status(claim_lines)
    message_parts.append(f"AGG={agg}")

    return {
        "segments": segments,
        "by_id": {k: v for k, v in by_id.items()},
        "ack_type": AcknowledgementType.X277,
        "status": agg,
        "affected_st02": _el(st, 2),
        "gs06": _el(gs, 6),
        "isa13": _el(isa, 13),
        "message": "; ".join(message_parts),
        "claim_statuses": claim_lines,
    }
