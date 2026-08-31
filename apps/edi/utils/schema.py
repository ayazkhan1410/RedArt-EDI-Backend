"""
Build X12 837P segment list from a payload dict (Colorado companion overlays).

Companion source: CO EDI v5010 X12 837P Companion Guide.
Full TR3 loop coverage will be refined later; this emits a valid-ordered
minimal FFS professional claim stream.
"""

from apps.edi.utils.envelope import DEFAULT_ENVELOPE

# Colorado Medical Assistance Program constants (companion guide).
CO_RECEIVER_ID = "COMEDASSISTPROG"
CO_RECEIVER_NAME = "COLORADO MEDICAL ASSISTANCE PROGRAM"
CO_PAYER_ID = "CO_TXIX"


def _sep(envelope):
    return envelope.get("element_separator") or DEFAULT_ENVELOPE["element_separator"]


def _term(envelope):
    return envelope.get("segment_terminator") or DEFAULT_ENVELOPE["segment_terminator"]


def _comp(envelope):
    return envelope.get("component_separator") or DEFAULT_ENVELOPE["component_separator"]


def _pad_isa(value, length=15):
    text = (value or "")[:length]
    return text.ljust(length)


def _seg(envelope, *parts):
    return _sep(envelope).join("" if p is None else str(p) for p in parts) + _term(
        envelope
    )


def build_edi_content(payload):
    """Return ordered list of X12 segment strings (each ends with ~)."""
    envelope = payload["envelope"]
    partner = payload["trading_partner"]
    control = payload["control"]
    claims = payload["claims"]
    cp = _comp(envelope)

    sender = partner["sender_id"]
    isa15 = envelope.get("isa15") or "T"
    isa13 = control["isa13"]
    gs06 = control["gs06"]
    when = payload["generated_at"]
    isa_date = when.strftime("%y%m%d")
    isa_time = when.strftime("%H%M")
    gs_date = when.strftime("%Y%m%d")
    gs_time = when.strftime("%H%M")
    gs08 = envelope.get("gs08") or DEFAULT_ENVELOPE["gs08"]
    rep = envelope.get("repetition_separator") or DEFAULT_ENVELOPE["repetition_separator"]

    edi_content = [
        _seg(
            envelope,
            "ISA",
            "00",
            " " * 10,
            "00",
            " " * 10,
            envelope.get("isa05") or "ZZ",
            _pad_isa(sender),
            envelope.get("isa07") or "ZZ",
            _pad_isa(CO_RECEIVER_ID),
            isa_date,
            isa_time,
            rep,
            "00501",
            isa13,
            "0",
            isa15,
            cp,
        ),
        _seg(
            envelope,
            "GS",
            envelope.get("gs01") or "HC",
            sender,
            CO_RECEIVER_ID,
            gs_date,
            gs_time,
            gs06,
            "X",
            gs08,
        ),
    ]

    st_count = 0
    for claim in claims:
        st_count += 1
        st02 = claim["st02"]
        provider = claim["provider"]
        patient = claim["patient"]
        st_start = len(edi_content)

        edi_content.append(_seg(envelope, "ST", "837", st02, gs08))
        edi_content.append(
            _seg(
                envelope,
                "BHT",
                "0019",
                "00",
                claim["claim_number"],
                gs_date,
                gs_time,
                "CH",
            )
        )

        # 1000A Submitter
        edi_content.append(
            _seg(
                envelope,
                "NM1",
                "41",
                "2",
                partner.get("name") or sender,
                "",
                "",
                "",
                "",
                "46",
                sender,
            )
        )
        phone = patient.get("phone") or provider.get("phone") or "0000000000"
        edi_content.append(
            _seg(envelope, "PER", "IC", partner.get("name") or "SUBMITTER", "TE", phone)
        )

        # 1000B Receiver (Colorado)
        edi_content.append(
            _seg(
                envelope,
                "NM1",
                "40",
                "2",
                CO_RECEIVER_NAME,
                "",
                "",
                "",
                "",
                "46",
                CO_RECEIVER_ID,
            )
        )

        # 2000A Billing provider HL (+ PRV specialty before 2010AA)
        billing_hl = 1
        edi_content.append(_seg(envelope, "HL", str(billing_hl), "", "20", "1"))
        if provider.get("taxonomy_code"):
            edi_content.append(
                _seg(envelope, "PRV", "BI", "PXC", provider["taxonomy_code"])
            )

        # 2010AA Billing Provider Name
        edi_content.append(
            _seg(
                envelope,
                "NM1",
                "85",
                "2",
                provider.get("billing_name") or provider.get("legal_name") or "PROVIDER",
                "",
                "",
                "",
                "",
                "XX",
                provider["npi"],
            )
        )
        if provider.get("address_line_1"):
            edi_content.append(_seg(envelope, "N3", provider["address_line_1"]))
            edi_content.append(
                _seg(
                    envelope,
                    "N4",
                    provider.get("city") or "",
                    provider.get("state") or "",
                    provider.get("zip") or "",
                )
            )
        # TR3: when NM108=XX (NPI), REF*EI (EIN/TIN) is required in 2010AA.
        tax_id = "".join(
            ch for ch in str(provider.get("tax_id") or "") if ch.isdigit()
        )
        if tax_id:
            edi_content.append(_seg(envelope, "REF", "EI", tax_id[:9]))

        # 2000B Subscriber HL (patient = subscriber per CO guide)
        edi_content.append(_seg(envelope, "HL", "2", str(billing_hl), "22", "0"))
        edi_content.append(_seg(envelope, "SBR", "P", "18", "", "", "", "", "", "", "MC"))
        edi_content.append(
            _seg(
                envelope,
                "NM1",
                "IL",
                "1",
                patient["last_name"],
                patient["first_name"],
                "",
                "",
                "",
                "MI",
                patient["medicaid_member_id"],
            )
        )
        edi_content.append(_seg(envelope, "N3", patient["address_line_1"]))
        edi_content.append(
            _seg(
                envelope,
                "N4",
                patient["city"],
                patient["state"],
                patient["zip"],
            )
        )
        edi_content.append(
            _seg(
                envelope,
                "DMG",
                "D8",
                patient["date_of_birth"],
                patient.get("gender") or "U",
            )
        )

        # 2010BB Payer
        edi_content.append(
            _seg(
                envelope,
                "NM1",
                "PR",
                "2",
                CO_RECEIVER_NAME,
                "",
                "",
                "",
                "",
                "PI",
                CO_PAYER_ID,
            )
        )

        # 2300 Claim — frequency 1 (original)
        pos = claim.get("place_of_service") or "41"
        clm05 = f"{pos}{cp}B{cp}1"
        edi_content.append(
            _seg(
                envelope,
                "CLM",
                claim["claim_number"],
                claim["total_charge"],
                "",
                "",
                clm05,
                "Y",
                "A",
                "Y",
                "Y",
            )
        )
        if claim.get("diagnosis_code"):
            diag = str(claim["diagnosis_code"]).replace(".", "")
            edi_content.append(_seg(envelope, "HI", f"ABK{cp}{diag}"))

        for idx, line in enumerate(claim.get("service_lines") or [], start=1):
            edi_content.append(_seg(envelope, "LX", str(idx)))
            proc = line.get("procedure_code") or "A0100"
            units = line.get("units") or 1
            charge = line.get("charge") or "0"
            edi_content.append(
                _seg(
                    envelope,
                    "SV1",
                    f"HC{cp}{proc}",
                    charge,
                    "UN",
                    units,
                    "",
                    "",
                    "1",
                )
            )
            if line.get("from_date"):
                edi_content.append(
                    _seg(envelope, "DTP", "472", "D8", line["from_date"])
                )

        # SE count includes ST through SE.
        body_count = len(edi_content) - st_start + 1
        edi_content.append(_seg(envelope, "SE", str(body_count), st02))

    edi_content.append(_seg(envelope, "GE", str(st_count), gs06))
    edi_content.append(_seg(envelope, "IEA", "1", isa13))
    return edi_content


def render_edi_file(edi_content):
    """Join segments with newlines (one segment per line)."""
    return "\n".join(edi_content) + ("\n" if edi_content else "")
