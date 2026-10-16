import csv
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from contractor_inquiry_intake.cli import main
from contractor_inquiry_intake.extract import Extractor
from contractor_inquiry_intake.models import CSV_COLUMNS, Inquiry
from contractor_inquiry_intake.pipeline import run
from contractor_inquiry_intake.storage import CSVStore, safe_cell

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def rows(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def test_all_ten_samples_csv_and_persistent_dedupe(tmp_path):
    paths = sorted(SAMPLES.iterdir())
    assert len(paths) == 10
    store = CSVStore(tmp_path / "inquiries.csv")
    batch = run(paths, store, Extractor())
    assert (batch.added, batch.duplicates, batch.errors) == (9, 1, 0)
    saved = rows(store.path)
    assert len(saved) == 9
    assert list(saved[0]) == list(CSV_COLUMNS)
    missing_location = next(row for row in saved if row["source"] == "05_missing_location.txt")
    assert missing_location["location"] == ""
    assert missing_location["missing"] == "location"
    assert "location" not in json.loads(missing_location["evidence"])
    assert ", OR" in saved[0]["location"]  # CSV quoting preserves embedded commas.
    second = run(paths, CSVStore(store.path), Extractor())
    assert (second.added, second.duplicates) == (0, 10)
    assert len(rows(store.path)) == 9
    assert "DUPLICATE" in batch.markdown()
    assert "MISSING: location" in batch.summary()


def test_normalized_duplicate_skips_extraction(tmp_path):
    first = tmp_path / "a.txt"
    second = tmp_path / "b.txt"
    first.write_text("Door repair\nContact: owner@example.com")
    second.write_text(" DOOR   REPAIR\n\nCONTACT: OWNER@EXAMPLE.COM\n")

    class CountingExtractor(Extractor):
        calls = 0

        def extract(self, inquiry):
            self.calls += 1
            return super().extract(inquiry)

    extractor = CountingExtractor()
    batch = run([first, second], CSVStore(tmp_path / "out.csv"), extractor)
    assert (batch.added, batch.duplicates, extractor.calls) == (1, 1, 1)


def test_changed_project_same_contact_is_new_inquiry(tmp_path):
    first = tmp_path / "a.txt"
    second = tmp_path / "b.txt"
    first.write_text("owner@example.com door repair")
    second.write_text("owner@example.com kitchen renovation")
    batch = run([first, second], CSVStore(tmp_path / "out.csv"), Extractor())
    assert batch.added == 2


def test_form_dedupe_is_independent_of_json_key_order(tmp_path):
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first.write_text('{"email":"owner@example.com","message":"door repair"}')
    second.write_text('{"message":"door repair", "email":"owner@example.com"}')
    assert Inquiry.from_path(first).inquiry_id == Inquiry.from_path(second).inquiry_id


@pytest.mark.parametrize("value", ["=1+1", "+cmd", "-cmd", "@SUM(1)", "\t=1", " \r+1"])
def test_csv_formula_guard(value):
    assert safe_cell(value).startswith("'")


def test_csv_roundtrips_multiline_and_neutralizes_formulas(tmp_path):
    path = tmp_path / "form.json"
    path.write_text(
        json.dumps({"name": "=1+1", "location": 'Room "A",\nElm Ridge', "message": "door repair"})
    )
    store = CSVStore(tmp_path / "out.csv")
    run([path], store, Extractor())
    saved = rows(store.path)[0]
    assert saved["name"] == "'=1+1"
    assert saved["location"] == 'Room "A",\nElm Ridge'


def test_concurrent_csv_append_is_deduped(tmp_path):
    path = tmp_path / "out.csv"
    row = dict.fromkeys(CSV_COLUMNS, "")
    row["inquiry_id"] = "same-id"

    def append(_):
        return CSVStore(path).append(row)

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(append, range(8))) == 1
    assert len(rows(path)) == 1


def test_existing_wrong_header_is_preserved(tmp_path):
    path = tmp_path / "out.csv"
    path.write_text("wrong,header\n")
    with pytest.raises(ValueError, match="header"):
        run(sorted(SAMPLES.iterdir()), CSVStore(path), Extractor())
    assert path.read_text() == "wrong,header\n"


def test_bad_input_does_not_stop_the_rest(tmp_path):
    invalid = tmp_path / "invalid.json"
    invalid.write_text("[1,2,3]")
    bad_type = tmp_path / "bad_type.json"
    bad_type.write_text('{"email": ["not a string"]}')
    empty = tmp_path / "empty.txt"
    empty.write_text(" \n")
    batch = run(
        [invalid, bad_type, empty, SAMPLES / "01_kitchen.txt"],
        CSVStore(tmp_path / "out.csv"),
        Extractor(),
    )
    assert (batch.added, batch.errors) == (1, 3)


def test_cli_table_and_no_external_integrations(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEET_ID", "fictional")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://invalid.example/webhook")
    path = tmp_path / "leads.csv"
    table = tmp_path / "table.md"
    assert (
        main(
            [
                str(SAMPLES),
                "--rules-only",
                "--local-only",
                "--csv",
                str(path),
                "--table",
                str(table),
            ]
        )
        == 0
    )
    assert "9 new, 1 duplicate, 0 error" in capsys.readouterr().out
    assert "05_missing_location.txt" in table.read_text()
    assert len(rows(path)) == 9


def test_cli_does_not_overwrite_an_input():
    with pytest.raises(SystemExit) as exc:
        main([str(SAMPLES / "01_kitchen.txt"), "--csv", str(SAMPLES / "01_kitchen.txt")])
    assert exc.value.code == 2
