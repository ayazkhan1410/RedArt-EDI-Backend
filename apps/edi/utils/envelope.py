"""ISA/GS envelope constants for 837P generation (not claim business data)."""

from django.conf import settings


DEFAULT_ENVELOPE = {
    "isa05": "ZZ",
    "isa07": "ZZ",
    "gs01": "HC",
    "gs08": "005010X222A1",
    "element_separator": "*",
    "component_separator": ":",
    "segment_terminator": "~",
    "repetition_separator": "^",
}


def get_edi_envelope_config(environment="TEST"):
    """
    Return ISA/GS constants for the given environment.
    Sender/receiver IDs come from TradingPartner at generate time.
    """
    configured = getattr(settings, "EDI_ENVELOPE", {}) or {}
    env = (environment or "TEST").strip().upper()
    usage = "P" if env == "PRODUCTION" else "T"

    return {
        "environment": env,
        "isa05": configured.get("isa05") or DEFAULT_ENVELOPE["isa05"],
        "isa07": configured.get("isa07") or DEFAULT_ENVELOPE["isa07"],
        "isa15": configured.get("isa15") or usage,
        "gs01": configured.get("gs01") or DEFAULT_ENVELOPE["gs01"],
        "gs08": configured.get("gs08") or DEFAULT_ENVELOPE["gs08"],
        "element_separator": configured.get("element_separator")
        or DEFAULT_ENVELOPE["element_separator"],
        "component_separator": configured.get("component_separator")
        or DEFAULT_ENVELOPE["component_separator"],
        "segment_terminator": configured.get("segment_terminator")
        or DEFAULT_ENVELOPE["segment_terminator"],
        "repetition_separator": configured.get("repetition_separator")
        or DEFAULT_ENVELOPE["repetition_separator"],
    }
