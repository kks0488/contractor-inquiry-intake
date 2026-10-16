"""CSV is the durable local ledger. Optional Sheets writes use RAW values."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from urllib.parse import quote

from filelock import FileLock

from .models import CSV_COLUMNS


def safe_cell(value: str) -> str:
    # Quoting CSV alone does not prevent spreadsheet formula evaluation.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


class CSVStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(str(path) + ".lock", timeout=30)

    def _ids_unlocked(self) -> set[str]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return set()
        with self.path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != list(CSV_COLUMNS):
                raise ValueError("existing CSV header does not match this schema")
            rows = list(reader)
            if any(None in row or any(v is None for v in row.values()) for row in rows):
                raise ValueError("existing CSV has a malformed row; restore it before appending")
            return {row["inquiry_id"] for row in rows}

    def ids(self) -> set[str]:
        with self.lock:
            return self._ids_unlocked()

    def append(self, row: dict[str, str]) -> bool:
        with self.lock:
            if row["inquiry_id"] in self._ids_unlocked():
                return False
            needs_header = not self.path.exists() or self.path.stat().st_size == 0
            with self.path.open("a", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
                if needs_header:
                    writer.writeheader()
                writer.writerow({key: safe_cell(row[key]) for key in CSV_COLUMNS})
                stream.flush()
                os.fsync(stream.fileno())
            return True


class SheetsSink:
    def __init__(self, sheet_id: str, sheet_range: str, credentials_path: str):
        self.sheet_id = sheet_id
        self.sheet_range = sheet_range
        self.credentials_path = credentials_path

    def append(self, rows: list[dict[str, str]]) -> None:
        # Optional dependency and credentials are loaded only when enabled.
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2.service_account import Credentials

        credentials = Credentials.from_service_account_file(
            self.credentials_path,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        url = (
            "https://sheets.googleapis.com/v4/spreadsheets/"
            f"{quote(self.sheet_id, safe='')}/values/{quote(self.sheet_range, safe='')}:append"
        )
        with AuthorizedSession(credentials) as session:
            response = session.post(
                url,
                params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                json={
                    "majorDimension": "ROWS",
                    "values": [[row[key] for key in CSV_COLUMNS] for row in rows],
                },
                timeout=30,
            )
            response.raise_for_status()
