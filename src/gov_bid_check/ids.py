"""UEI, CAGE, and sample NAICS checks.

Format rules follow fitzyracing1/spin-gov-contracting (published format only,
not a live SAM.gov or DLA lookup):

- UEI: 12 alphanumeric characters, no I or O, first character is not 0.
- US CAGE: 5 alphanumeric characters excluding I and O, fifth character is a digit.
- NAICS in this tool: 6 digits, looked up in a bundled SAMPLE size-standard table.
"""

from __future__ import annotations

import csv
import re
from decimal import Decimal
from pathlib import Path

UEI_RE = re.compile(r"^[A-HJ-NP-Z0-9]{12}$")
US_CAGE_RE = re.compile(r"^[0-9A-HJ-NP-Z]{4}[0-9]$")
NCAGE_RE = re.compile(r"^[0-9A-HJ-NP-Z]{5}$")
NAICS_RE = re.compile(r"^\d{6}$")
SAMPLE_PATH = Path(__file__).resolve().parent / "data" / "SAMPLE_NAICS_SIZE_STANDARDS.csv"
SAMPLE_DISCLAIMER = (
    "SAMPLE table only — not official SBA size standards. "
    "Do not use this for eligibility, filing, or certification."
)


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


def check_uei(value: str) -> dict:
    raw = value.strip()
    code = normalize(raw)
    issues: list[str] = []
    if raw and not re.fullmatch(r"[A-Za-z0-9]+", raw.replace(" ", "")):
        issues.append("only letters and digits are allowed (no hyphens or punctuation)")
    if len(code) != 12:
        issues.append(f"must be exactly 12 characters, got {len(code)}")
    if any(ch in code for ch in "IO"):
        issues.append("letters I and O are not used (they can be confused with 1 and 0)")
    if code.startswith("0"):
        issues.append("the first character is never zero")
    ok = not issues and bool(UEI_RE.match(code))
    return {
        "kind": "UEI",
        "value": code,
        "ok": ok,
        "issues": issues,
        "note": "Format only; does not prove the ID is assigned or active on SAM.gov.",
        "rules": "12 alphanumeric characters, no I or O, first character is not 0.",
    }


def check_cage(value: str, *, ncage: bool = False) -> dict:
    code = normalize(value)
    issues: list[str] = []
    if len(code) != 5:
        issues.append(f"must be exactly 5 characters, got {len(code)}")
    if not re.fullmatch(r"[A-Z0-9]*", code):
        issues.append("only letters and digits are allowed")
    if any(ch in code for ch in "IO"):
        issues.append("letters I and O are not used")
    if ncage:
        ok = not issues and bool(NCAGE_RE.match(code))
        kind = "NCAGE"
        rules = "5 alphanumeric characters excluding I and O (NATO NCAGE shape)."
        note = "Format only; this is not a DLA or NSPA assignment check."
    else:
        if code and not code[-1].isdigit():
            issues.append("a US CAGE has a digit in the fifth position (DLA)")
        ok = not issues and bool(US_CAGE_RE.match(code))
        kind = "CAGE"
        rules = "5 alphanumeric characters excluding I and O, fifth character is a digit (US CAGE, DLA)."
        note = "Format only; verify an assigned code at https://cage.dla.mil."
    return {
        "kind": kind,
        "value": code,
        "ok": ok,
        "issues": issues,
        "note": note,
        "rules": rules,
    }


def load_sample_naics(path: Path = SAMPLE_PATH) -> dict:
    rows = {}
    with path.open(encoding="utf-8") as handle:
        lines = [line for line in handle if line.strip() and not line.lstrip().startswith("#")]
    reader = csv.DictReader(lines)
    for row in reader:
        rows[row["naics"].strip()] = {
            "naics": row["naics"].strip(),
            "title": row["title"].strip(),
            "size_standard": Decimal(row["size_standard"].strip()),
            "unit": row["unit"].strip(),
        }
    return rows


def lookup_naics(code: str, *, receipts=None, employees=None, table=None) -> dict:
    code = re.sub(r"\D", "", str(code))
    issues: list[str] = []
    if not NAICS_RE.match(code):
        issues.append("NAICS codes in this tool are 6 digits")
        return {
            "ok": False,
            "code": code,
            "issues": issues,
            "row": None,
            "comparison": None,
            "disclaimer": SAMPLE_DISCLAIMER,
            "missing": False,
        }
    table = load_sample_naics() if table is None else table
    row = table.get(code)
    if row is None:
        return {
            "ok": True,
            "code": code,
            "issues": [],
            "row": None,
            "comparison": None,
            "disclaimer": SAMPLE_DISCLAIMER,
            "missing": True,
        }
    comparison = None
    if receipts is not None or employees is not None:
        if row["unit"] == "receipts_usd":
            if receipts is None:
                comparison = "this sample standard is in receipts; pass receipts to compare"
            else:
                given = Decimal(str(receipts))
                comparison = (
                    "under the sample receipts threshold"
                    if given <= row["size_standard"]
                    else "over the sample receipts threshold"
                )
        else:
            if employees is None:
                comparison = "this sample standard is in employees; pass employees to compare"
            else:
                given = Decimal(str(employees))
                comparison = (
                    "under the sample employee threshold"
                    if given <= row["size_standard"]
                    else "over the sample employee threshold"
                )
    return {
        "ok": True,
        "code": code,
        "issues": [],
        "row": row,
        "comparison": comparison,
        "disclaimer": SAMPLE_DISCLAIMER,
        "missing": False,
    }
