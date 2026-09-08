"""Required-data checks for Colorado 837P generation.

Never fabricate subscriber demographics. DOB/gender are optional here; when
verified demographics are present they may be emitted as DMG, otherwise DMG is
omitted.
"""

from datetime import date, datetime
import re


def subscriber_errors(dob, gender):
    """Validate subscriber demographics only when they are actually supplied."""
    errors = []
    if dob:
        try:
            if isinstance(dob, datetime):
                value = dob.date()
            elif isinstance(dob, date):
                value = dob
            else:
                text = str(dob).strip()
                if re.fullmatch(r"[0-9]{8}", text):
                    value = datetime.strptime(text, "%Y%m%d").date()
                else:
                    value = date.fromisoformat(text)
            if value > date.today():
                raise ValueError()
        except (ValueError, TypeError):
            errors.append("Subscriber date_of_birth, when supplied, must be a valid, non-future date.")
    if gender and str(gender).strip().upper() not in {"M", "F", "U"}:
        errors.append("Subscriber gender, when supplied, must be M, F, or U.")
    return errors


def billing_address_errors(provider):
    errors = []
    for field in ("address_line_1", "city", "state", "zip"):
        if not str(provider.get(field) or "").strip():
            errors.append(f"Billing provider {field} is required for 2010AA N3/N4.")
    postal = str(provider.get("zip") or "").strip()
    if postal and not re.fullmatch(r"[0-9]{5}(?:[0-9]{4}|-[0-9]{4})?", postal):
        errors.append("Billing provider zip must be a real 5-digit ZIP or ZIP+4; never pad or invent digits.")
    return errors


def x12_required_data_errors(raw):
    """Apply RedArt safety checks to the exact bytes to send."""
    text = (raw or "").lstrip("\ufeff\r\n\t ")
    if not text.startswith("ISA") or len(text) < 106:
        return []  # pyx12 reports malformed envelopes.
    separator, terminator = text[3], text[105]
    errors = []
    loop = None
    has_billing_n4 = False
    for segment in text.split(terminator):
        fields = segment.strip().split(separator)
        tag = fields[0]
        value = lambda index: fields[index] if len(fields) > index else ""
        if tag == "ST":
            has_billing_n4 = False
            loop = None
        if tag == "NM1":
            if loop == "85" and not has_billing_n4:
                errors.append("Billing provider 2010AA N4 is missing.")
            loop = value(1)
        if tag == "N4" and loop == "85":
            has_billing_n4 = True
            if not value(3).strip():
                errors.append("Billing provider zip is missing in 2010AA N403.")
        if tag == "DMG" and loop == "IL":
            errors.extend(subscriber_errors(value(2), value(3)))
    return errors
