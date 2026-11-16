"""Check draft bid/registration records for format issues."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from gov_bid_check.ids import SAMPLE_DISCLAIMER, check_cage, check_uei, lookup_naics

REQUIRED_FIELDS = ("entity_name", "uei", "cage", "naics")
RECOMMENDED_FIELDS = ("deadline", "email")

NAME_ALIASES = ("entity_name", "legal_name", "name", "vendor_name", "company", "organization")
UEI_ALIASES = ("uei", "unique_entity_id", "unique entity id")
CAGE_ALIASES = ("cage", "cage_code", "cagecode")
NAICS_ALIASES = ("naics", "naics_code", "naics_codes")
DEADLINE_ALIASES = (
    "deadline",
    "due_date",
    "due",
    "submission_deadline",
    "response_date",
    "closing_date",
)
EMAIL_ALIASES = ("email", "poc_email", "point_of_contact", "poc", "contact_email")
RECEIPTS_ALIASES = ("receipts", "annual_receipts", "revenue")
EMPLOYEES_ALIASES = ("employees", "employee_count", "headcount")

DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%d-%b-%Y", "%B %d, %Y", "%Y-%m-%dT%H:%M:%S")


@dataclass
class Finding:
    severity: str  # error or warning
    field: str
    message: str

    def line(self) -> str:
        return f"  [{self.severity}] {self.field}: {self.message}"


@dataclass
class RecordResult:
    index: int
    findings: list[Finding] = field(default_factory=list)
    values: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not any(f.severity == "error" for f in self.findings)


@dataclass
class CheckResult:
    source: str
    records: list[RecordResult] = field(default_factory=list)
    parse_error: str | None = None

    @property
    def ok(self) -> bool:
        if self.parse_error:
            return False
        return all(record.ok for record in self.records)

    def report(self) -> str:
        lines = [
            "gov-bid-check report",
            "FORMAT PRE-CHECK ONLY — not legal advice, not official verification,",
            "and not a SAM.gov, DLA, or SBA lookup. No network calls are made.",
            SAMPLE_DISCLAIMER,
            f"Source: {self.source}",
            "",
        ]
        if self.parse_error:
            lines.append(f"  [error] parse: {self.parse_error}")
            lines.append("")
            return "\n".join(lines)
        if not self.records:
            lines.append("  [error] parse: no records found")
            lines.append("")
            return "\n".join(lines)
        for record in self.records:
            label = f"record {record.index}"
            name = record.values.get("entity_name")
            if name:
                label += f" ({name})"
            status = "ok" if record.ok else "issues found"
            lines.append(f"{label}: {status}")
            if not record.findings:
                lines.append("  no issues")
            else:
                for finding in record.findings:
                    lines.append(finding.line())
            lines.append("")
        return "\n".join(lines)


def _lower_keys(record: dict) -> dict:
    out = {}
    for key, value in record.items():
        if key is None:
            continue
        out[str(key).strip().lower().replace("-", "_").replace(" ", "_")] = value
    return out


def _first(record: dict, aliases: tuple[str, ...]) -> tuple[str | None, Any]:
    for alias in aliases:
        if alias in record and record[alias] not in (None, ""):
            return alias, record[alias]
    return None, None


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    # fromisoformat handles YYYY-MM-DD and YYYY-MM-DDTHH:MM:SS
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.date()
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def check_record(record: dict, *, as_of: date | None = None, index: int = 1, ncage: bool = False) -> RecordResult:
    """Check one draft bid/registration mapping."""
    as_of = as_of or date.today()
    data = _lower_keys(record)
    result = RecordResult(index=index)
    findings: list[Finding] = []

    _, name = _first(data, NAME_ALIASES)
    if name is None:
        findings.append(
            Finding("error", "entity_name", "required field is missing (also accepted: legal_name, name, vendor_name)")
        )
    else:
        result.values["entity_name"] = str(name).strip()

    _, uei_val = _first(data, UEI_ALIASES)
    if uei_val is None:
        findings.append(Finding("error", "uei", "required field is missing"))
    else:
        checked = check_uei(str(uei_val))
        result.values["uei"] = checked["value"]
        if not checked["ok"]:
            for issue in checked["issues"]:
                findings.append(Finding("error", "uei", issue))

    _, cage_val = _first(data, CAGE_ALIASES)
    if cage_val is None:
        findings.append(Finding("error", "cage", "required field is missing"))
    else:
        checked = check_cage(str(cage_val), ncage=ncage)
        result.values["cage"] = checked["value"]
        if not checked["ok"]:
            for issue in checked["issues"]:
                findings.append(Finding("error", "cage", issue))

    _, naics_val = _first(data, NAICS_ALIASES)
    if naics_val is None:
        findings.append(Finding("error", "naics", "required field is missing"))
    else:
        # If several codes are given, check the first.
        first_code = str(naics_val).split(",")[0].strip()
        _, receipts = _first(data, RECEIPTS_ALIASES)
        _, employees = _first(data, EMPLOYEES_ALIASES)
        looked = lookup_naics(first_code, receipts=receipts, employees=employees)
        result.values["naics"] = looked["code"]
        if not looked["ok"]:
            for issue in looked["issues"]:
                findings.append(Finding("error", "naics", issue))
        else:
            if looked.get("missing"):
                findings.append(
                    Finding(
                        "warning",
                        "naics",
                        f"{looked['code']} is 6 digits but is not in the bundled sample table "
                        "(that does not mean the code is invalid)",
                    )
                )
            elif looked.get("row"):
                row = looked["row"]
                unit = "USD receipts" if row["unit"] == "receipts_usd" else "employees"
                msg = f"sample title {row['title']!r}; sample standard {row['size_standard']} {unit}"
                if looked.get("comparison"):
                    msg += f"; {looked['comparison']}"
                findings.append(Finding("warning", "naics", msg))
        # Disclaimer is printed once in the report header, not on every record.

    _, deadline_val = _first(data, DEADLINE_ALIASES)
    if deadline_val is None:
        findings.append(
            Finding("warning", "deadline", "recommended field is missing (due_date, submission_deadline, closing_date)")
        )
    else:
        parsed = _parse_date(deadline_val)
        if parsed is None:
            findings.append(
                Finding("error", "deadline", f"could not parse date {deadline_val!r}; use YYYY-MM-DD")
            )
        else:
            result.values["deadline"] = parsed.isoformat()
            if parsed < as_of:
                findings.append(
                    Finding(
                        "error",
                        "deadline",
                        f"{parsed.isoformat()} is in the past (as of {as_of.isoformat()})",
                    )
                )

    _, email = _first(data, EMAIL_ALIASES)
    if email is None:
        findings.append(Finding("warning", "email", "recommended field is missing (poc, poc_email, point_of_contact)"))
    else:
        result.values["email"] = str(email).strip()

    result.findings = findings
    return result


def check_records(records: list[dict], *, source: str, as_of: date | None = None, ncage: bool = False) -> CheckResult:
    result = CheckResult(source=source)
    for index, record in enumerate(records, start=1):
        result.records.append(check_record(record, as_of=as_of, index=index, ncage=ncage))
    return result


def check_text(text: str, *, source: str = "input", hint: str | None = None, as_of: date | None = None, ncage: bool = False) -> CheckResult:
    from gov_bid_check.parse import ParseError, parse_text

    try:
        records = parse_text(text, hint=hint)
    except (ParseError, ValueError) as exc:
        return CheckResult(source=source, parse_error=str(exc))
    return check_records(records, source=source, as_of=as_of, ncage=ncage)
