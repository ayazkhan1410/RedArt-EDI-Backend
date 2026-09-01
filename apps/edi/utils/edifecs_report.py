"""Parse Edifecs STCO validation reports (Summary / Audit / LDNS XML)."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

from apps.edi.choices import ValidationReportStatus, ValidationReportType


def _text(elem, default=None):
    if elem is None:
        return default
    text = (elem.text or "").strip()
    return text or default


def _attr(elem, name, default=None):
    if elem is None:
        return default
    return elem.attrib.get(name, default)


def _parse_int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _parse_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def _map_status_code(code: str | None, audit_status: str | None = None) -> str:
    code = (code or "").strip().upper()
    audit = (audit_status or "").strip().upper()
    if audit == "PASSED" or code == "A":
        return ValidationReportStatus.PASSED
    if code in ("A", "ACCEPTED"):
        return ValidationReportStatus.ACCEPTED
    if code in ("R", "REJECTED"):
        return ValidationReportStatus.REJECTED
    if code in ("P", "PARTIAL"):
        return ValidationReportStatus.PARTIAL
    if code in ("E", "ERROR", "F", "FAILED"):
        return ValidationReportStatus.FAILED
    return ValidationReportStatus.UNKNOWN


def _detect_report_type(root_tag: str, file_name: str | None = None) -> str:
    tag = (root_tag or "").lower()
    name = (file_name or "").upper()
    if "datareport" in tag or "LDNS" in name:
        return ValidationReportType.LDNS
    if "auditreport" in tag or "AUDIT" in name:
        return ValidationReportType.AUDIT
    return ValidationReportType.SUMMARY


def _field_value(root, name: str):
    for field in root.iter("Field"):
        if _attr(field, "Name") == name:
            return _text(field)
    return None


def parse_edifecs_report(content: str, *, file_name: str | None = None) -> dict:
    """
    Parse Edifecs AuditReport or DataReport XML into normalized dict.
  Raises ValueError on empty/invalid XML.
    """
    text = (content or "").strip()
    if not text:
        raise ValueError("Report content is empty.")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid XML report: {exc}") from exc

    report_type = _detect_report_type(root.tag, file_name=file_name)
    task_id = _text(root.find("TaskID")) or _attr(root, "TaskID")
    report_guid = _attr(root, "Guid") or _attr(root, "GUID")

    data_file = root.find("DataFile")
    file_name_parsed = _text(data_file.find("FileName")) if data_file is not None else None
    file_size = _parse_int(_text(data_file.find("FileSize")), 0) if data_file is not None else 0

    audit_status = _text(root.find("AuditStatus")) or _attr(root, "AuditStatus")
    status_code = _attr(root, "StatusCode") or _attr(root, "STATUSCODE")
    status = _map_status_code(status_code, audit_status)

    error_count = _parse_int(_attr(root, "NumberOfErrors"), 0)
    if error_count == 0 and root.find("ErrorStatistics") is not None:
        stats = root.find("ErrorStatistics")
        error_count = _parse_int(_text(stats.find("ErrorCount")), 0)

    accepted_claims = None
    accepted_charge = None
    ac = _field_value(root, "AcceptedClaims")
    if ac is not None:
        accepted_claims = _parse_int(ac, 0)
    charge = _field_value(root, "AcceptedClaimCharge")
    if charge is not None:
        accepted_charge = _parse_decimal(charge)

    message_parts = []
    if audit_status:
        message_parts.append(f"AuditStatus={audit_status}")
    if status_code:
        message_parts.append(f"StatusCode={status_code}")
    if error_count:
        message_parts.append(f"Errors={error_count}")

    file_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    return {
        "report_type": report_type,
        "status": status,
        "task_id": task_id,
        "report_guid": report_guid,
        "file_name": file_name_parsed or file_name,
        "file_size": file_size,
        "error_count": error_count,
        "accepted_claims": accepted_claims,
        "accepted_charge": accepted_charge,
        "file_hash": file_hash,
        "message": "; ".join(message_parts) or None,
        "parsed_summary": {
            "root_tag": root.tag,
            "audit_status": audit_status,
            "status_code": status_code,
            "task_id": task_id,
            "report_guid": report_guid,
            "accepted_claims": accepted_claims,
            "accepted_charge": str(accepted_charge) if accepted_charge is not None else None,
        },
    }


def compute_report_hash(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()
