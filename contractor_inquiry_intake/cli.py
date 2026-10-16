"""CLI for saved email text and web form JSON; no public web server required."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from filelock import Timeout

from .extract import Extractor
from .pipeline import notify_slack, run
from .storage import CSVStore, SheetsSink


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="one .txt/.eml/.json file or a directory")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("data/inquiries.csv"),
        help="local ledger and dedupe scope (default: data/inquiries.csv)",
    )
    parser.add_argument("--rules-only", action="store_true", help="offline, even with a key set")
    parser.add_argument("--table", type=Path, help="also write the batch result as Markdown")
    parser.add_argument("--local-only", action="store_true", help="disable Sheets and Slack")
    args = parser.parse_args(argv)
    suffixes = {".txt", ".eml", ".json"}
    if args.input.is_dir():
        paths = sorted(
            p for p in args.input.iterdir() if p.is_file() and p.suffix.lower() in suffixes
        )
    else:
        paths = (
            [args.input] if args.input.is_file() and args.input.suffix.lower() in suffixes else []
        )
    if not paths:
        parser.error("no supported input files found")
    # Output must not overwrite an inquiry or the CSV, including through symlinks.
    inputs = {p.resolve() for p in paths}
    if args.csv.resolve() in inputs or (
        args.table
        and (args.table.resolve() in inputs or args.table.resolve() == args.csv.resolve())
    ):
        parser.error("input, CSV and table paths must be different")

    sheets = None
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")
    credentials = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not args.local_only and sheet_id:
        sheets = SheetsSink(
            sheet_id, os.environ.get("GOOGLE_SHEET_RANGE", "Inquiries!A:N"), credentials
        )
    try:
        batch = run(
            paths, CSVStore(args.csv), Extractor.from_env(rules_only=args.rules_only), sheets
        )
    except (OSError, ValueError, Timeout):
        print(
            "Could not open or append the CSV ledger. Check path, header and permissions.",
            file=sys.stderr,
        )
        return 1
    print(batch.summary())
    print()
    print(batch.markdown())
    if args.table:
        try:
            args.table.parent.mkdir(parents=True, exist_ok=True)
            args.table.write_text(batch.markdown() + "\n", encoding="utf-8")
        except OSError:
            print("CSV saved, but the Markdown table could not be written.", file=sys.stderr)
            return 1
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    if webhook and not args.local_only and batch.added:
        if not notify_slack(batch.summary(), webhook):
            print("Slack notification failed; CSV is saved.", file=sys.stderr)
    return 1 if batch.errors else 0
