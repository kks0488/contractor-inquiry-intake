import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from contractor_inquiry_intake.extract import Extractor
from contractor_inquiry_intake.models import CSV_COLUMNS
from contractor_inquiry_intake.pipeline import notify_slack, run
from contractor_inquiry_intake.storage import CSVStore, SheetsSink

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def test_sheets_failure_keeps_csv_and_does_not_reappend_duplicates(tmp_path):
    sink = MagicMock()
    sink.append.side_effect = RuntimeError("secret should not be logged")
    store = CSVStore(tmp_path / "out.csv")
    batch = run(sorted(SAMPLES.iterdir()), store, Extractor(), sink)
    assert batch.added == 9
    assert len(store.ids()) == 9
    assert len(sink.append.call_args.args[0]) == 9
    assert batch.warnings == ["Sheets append failed; all new rows remain in local CSV"]
    run(sorted(SAMPLES.iterdir()), store, Extractor(), sink)
    assert sink.append.call_count == 1


def test_sheets_uses_service_account_raw_values_and_column_order():
    row = dict.fromkeys(CSV_COLUMNS, "")
    row["name"] = "=1+1"
    with (
        patch("google.oauth2.service_account.Credentials.from_service_account_file") as creds,
        patch("google.auth.transport.requests.AuthorizedSession") as session,
    ):
        SheetsSink("demo-sheet", "Inquiries!A:N", "/outside/repo/credentials.json").append([row])
        creds.assert_called_once_with(
            "/outside/repo/credentials.json",
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        request = session.return_value.__enter__.return_value.post.call_args
        assert "Inquiries%21A%3AN:append" in request.args[0]
        assert request.kwargs["params"]["valueInputOption"] == "RAW"
        assert request.kwargs["json"]["values"] == [[row[key] for key in CSV_COLUMNS]]


def test_slack_is_plain_text_and_handles_failures():
    def handler(request):
        payload = json.loads(request.content)
        assert payload["blocks"][0]["text"]["type"] == "plain_text"
        assert payload["blocks"][0]["text"]["text"] == "new lead <@everyone>"
        return httpx.Response(200, text="ok")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert notify_slack("new lead <@everyone>", "https://example.com/webhook", client=client)
    failing = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(500, text="not logged"))
    )
    assert not notify_slack("summary", "https://example.com/webhook", client=failing)
