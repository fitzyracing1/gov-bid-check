"""Parse a draft bid/registration file: JSON, simple YAML, or CSV."""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path


class ParseError(ValueError):
    pass


def _strip_comment_line(line: str) -> str:
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return ""
    return line


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_simple_yaml(text: str) -> list[dict]:
    """Parse a restricted YAML subset: a mapping, or a list of mappings."""
    lines = []
    for raw in text.splitlines():
        if not _strip_comment_line(raw).strip():
            continue
        # Inline comment after a value, when not inside quotes.
        if "#" in raw:
            in_quote = False
            buf = []
            for ch in raw:
                if ch in {'"', "'"}:
                    in_quote = not in_quote
                    buf.append(ch)
                elif ch == "#" and not in_quote:
                    break
                else:
                    buf.append(ch)
            raw = "".join(buf)
        if raw.strip():
            lines.append(raw.rstrip())
    if not lines:
        raise ParseError("The YAML file is empty.")

    # List of mappings.
    if any(line.lstrip().startswith("- ") for line in lines):
        records: list[dict] = []
        current: dict | None = None
        item_indent = None
        for line in lines:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if stripped.startswith("- "):
                current = {}
                records.append(current)
                item_indent = indent
                rest = stripped[2:].strip()
                if rest and ":" in rest:
                    key, _, val = rest.partition(":")
                    current[key.strip()] = _unquote(val)
                continue
            if current is None:
                raise ParseError("YAML list item is missing a `- ` marker.")
            if ":" not in stripped:
                raise ParseError(f"Cannot parse YAML line: {line}")
            key, _, val = stripped.partition(":")
            current[key.strip()] = _unquote(val)
        return records

    record: dict = {}
    for line in lines:
        if line.startswith(" ") or line.startswith("\t"):
            raise ParseError(
                "Nested YAML is not supported in this helper; use a flat mapping, a list of mappings, JSON, or CSV."
            )
        if ":" not in line:
            raise ParseError(f"Cannot parse YAML line: {line}")
        key, _, val = line.partition(":")
        record[key.strip()] = _unquote(val)
    return [record]


def parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ParseError("CSV file has no header row.")
    records = []
    for row in reader:
        records.append({(k or "").strip(): (v or "").strip() for k, v in row.items()})
    if not records:
        raise ParseError("CSV file has a header but no data rows.")
    return records


def parse_text(text: str, hint: str | None = None) -> list[dict]:
    """Parse text as JSON, CSV, or simple YAML, using hint (suffix or format name) when given."""
    stripped = text.strip()
    hint = (hint or "").lower().lstrip(".")
    if hint in {"json"}:
        data = json.loads(stripped)
        return _as_records(data)
    if hint in {"csv"}:
        return parse_csv(text)
    if hint in {"yml", "yaml"}:
        return parse_simple_yaml(text)

    # Autodetect.
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return _as_records(json.loads(stripped))
        except json.JSONDecodeError:
            pass
    if hint or "," in text.splitlines()[0] if text.splitlines() else False:
        first = next((line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")), "")
        if first.count(",") >= 2 and ":" not in first.split(",")[0]:
            return parse_csv(text)
    return parse_simple_yaml(text)


def _as_records(data):
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        return data
    raise ParseError("JSON must be an object or a list of objects.")


def parse_path(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    return parse_text(text, hint=path.suffix)
