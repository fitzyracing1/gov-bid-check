"""Tests for gov-bid-check. Sample files are fixtures, not real registrations."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from gov_bid_check.check import check_record, check_text
from gov_bid_check.cli import main
from gov_bid_check.ids import check_cage, check_uei, lookup_naics
from gov_bid_check.parse import parse_path

SAMPLES = Path(__file__).parent / "samples"
AS_OF = date(2026, 11, 15)


def test_uei_and_cage_format_rules():
    assert check_uei("J6H4FB3N5YK4")["ok"] is True
    assert check_uei("06H4FB3N5YK4")["ok"] is False  # leading zero
    assert check_uei("J6H4FB3N5YK")["ok"] is False  # 11 chars
    assert check_uei("I6H4FB3N5YK4")["ok"] is False  # letter I
    assert check_cage("0YWL3")["ok"] is True
    assert check_cage("12AB")["ok"] is False
    assert check_cage("ABCDE")["ok"] is False  # US CAGE needs a final digit
    assert check_cage("ABCDE", ncage=True)["ok"] is True


def test_sample_naics_lookup_is_labeled_sample():
    result = lookup_naics("541511", receipts="5000000")
    assert result["ok"] is True
    assert result["missing"] is False
    assert "under" in result["comparison"]
    assert "SAMPLE" in result["disclaimer"]
    assert "not official" in result["disclaimer"].lower()
    missing = lookup_naics("999999")
    assert missing["ok"] is True
    assert missing["missing"] is True
    bad = lookup_naics("54")
    assert bad["ok"] is False


def test_good_yaml_passes(tmp_path=None):
    text = (SAMPLES / "good.yaml").read_text(encoding="utf-8")
    result = check_text(text, source="good.yaml", hint="yaml", as_of=AS_OF)
    assert result.ok
    record = result.records[0]
    assert record.values["uei"] == "J6H4FB3N5YK4"
    assert record.values["cage"] == "0YWL3"
    assert any("sample title" in f.message for f in record.findings)
    report = result.report()
    assert "FORMAT PRE-CHECK ONLY" in report
    assert "not official" in report.lower()
    assert "SAM.gov" in report


def test_bad_json_flags_each_problem():
    text = (SAMPLES / "bad.json").read_text(encoding="utf-8")
    result = check_text(text, source="bad.json", hint="json", as_of=AS_OF)
    assert not result.ok
    fields = {f.field for f in result.records[0].findings if f.severity == "error"}
    assert "uei" in fields  # leading zero
    assert "cage" in fields  # only 4 chars
    assert "naics" in fields  # not 6 digits
    assert "deadline" in fields  # 2020-01-15 is past
    report = result.report()
    assert "first character is never zero" in report
    assert "2020-01-15 is in the past" in report


def test_csv_two_records_and_aliases():
    records = parse_path(SAMPLES / "two.csv")
    assert len(records) == 2
    text = (SAMPLES / "two.csv").read_text(encoding="utf-8")
    result = check_text(text, source="two.csv", hint="csv", as_of=AS_OF)
    assert result.ok
    assert result.records[0].values["entity_name"] == "Sample Robotics LLC"
    assert result.records[1].values["entity_name"] == "Second Co"
    assert result.records[1].values["naics"] == "236220"


def test_missing_required_fields():
    result = check_record({}, as_of=AS_OF)
    fields = {f.field for f in result.findings if f.severity == "error"}
    assert fields == {"entity_name", "uei", "cage", "naics"}


def test_deadline_today_is_not_past():
    result = check_record(
        {
            "name": "A",
            "uei": "J6H4FB3N5YK4",
            "cage": "0YWL3",
            "naics": "541511",
            "deadline": "2026-11-15",
        },
        as_of=AS_OF,
    )
    assert not any(f.field == "deadline" and f.severity == "error" for f in result.findings)


def test_cli_write_does_not_overwrite(tmp_path, capsys):
    src = tmp_path / "bid.yaml"
    original = (SAMPLES / "good.yaml").read_text(encoding="utf-8")
    src.write_text(original, encoding="utf-8")
    assert main([str(src), "--as-of", "2026-11-15", "--write"]) == 0
    assert src.read_text(encoding="utf-8") == original
    dest = tmp_path / "bid.tidy.txt"
    assert dest.is_file()
    text = dest.read_text(encoding="utf-8")
    assert "FORMAT PRE-CHECK ONLY" in text
    assert "ok" in text
    assert "Wrote" in capsys.readouterr().err


def test_cli_bad_file_exits_one(capsys):
    assert main([str(SAMPLES / "bad.json"), "--as-of", "2026-11-15"]) == 1
    out = capsys.readouterr().out
    assert "issues found" in out
