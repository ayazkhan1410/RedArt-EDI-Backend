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
