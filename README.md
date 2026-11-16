# gov-bid-check

Format pre-check for a draft bid or registration file (YAML, JSON, or CSV).

This tool checks **shape and completeness only**. It is **not legal advice**, **not official verification**, and **not a SAM.gov, DLA, or SBA lookup**. It never makes a network call. A format-valid UEI or CAGE is not proof that the ID is assigned or active.

It builds on the format rules in [spin-gov-contracting](https://github.com/fitzyracing1/spin-gov-contracting). Sponsor: [github.com/sponsors/fitzyracing1](https://github.com/sponsors/fitzyracing1).

## Install

```bash
pipx install git+https://github.com/fitzyracing1/gov-bid-check
```

Or from a checkout:

```bash
pip install -e .
```

## Usage

```bash
gov-bid-check bid.yaml
python -m gov_bid_check bid.json
gov-bid-check registrations.csv
```

Write the report to `bid.tidy.txt` (the input file is never overwritten):

```bash
gov-bid-check --write bid.yaml
```

Compare deadlines to a fixed date (useful in tests; defaults to today):

```bash
gov-bid-check bid.yaml --as-of 2026-11-15
```

The process exits `1` when any record has an error, and `0` when every record is format-ok.

## What it checks

- **UEI** — 12 alphanumeric characters, no letters I or O, first character is not 0.
- **CAGE** — 5 alphanumeric characters excluding I and O, fifth character is a digit (US CAGE). Use `--ncage` for the broader 5-character NCAGE shape.
- **NAICS** — 6-digit shape, plus an optional lookup in a bundled **sample** size-standard table (clearly labeled sample data, not official SBA standards). If the record includes `receipts` or `employees`, the helper compares them to that sample threshold.
- **Required fields** — `entity_name` (aliases: `legal_name`, `name`, `vendor_name`), `uei`, `cage`, `naics`.
- **Deadlines** — `deadline` / `due_date` / `submission_deadline` / `closing_date` must parse (prefer `YYYY-MM-DD`) and must not be in the past. A missing deadline is a warning, not an error.

NAICS rows live in `src/gov_bid_check/data/SAMPLE_NAICS_SIZE_STANDARDS.csv` and are marked `SAMPLE DATA — NOT official SBA size standards`.

## License

MIT. Copyright (c) 2026 Joshua Almeida (fitzyracing1).
