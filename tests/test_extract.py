import json
from pathlib import Path

import httpx
import pytest

from contractor_inquiry_intake.extract import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    Extractor,
    literal_span,
    rule_extract,
)
from contractor_inquiry_intake.models import FIELDS, Inquiry, Lead

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def test_complete_email():
    lead = rule_extract(Inquiry.from_path(SAMPLES / "01_kitchen.txt"))
    assert lead.name == "Maya Ellis"
    assert lead.email == "maya.ellis@example.com"
    assert lead.phone == "202-555-0101"
    assert lead.project_type.casefold() == "kitchen renovation"
    assert lead.location == "Cedar Hollow, OR"
    assert lead.timeline == "next month"
    assert lead.budget_hint == "$18,000-$22,000"
    assert lead.missing == []


def test_form_values_are_authoritative():
    lead = rule_extract(Inquiry.from_path(SAMPLES / "02_bookshelves.json"))
    assert lead.name == "Jonah Reed"
    assert lead.project_type == "custom bookshelves"
    assert lead.budget_hint == "$4,500"
    assert lead.missing == []


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("04_bathroom.txt", ["budget_hint"]),
        ("05_missing_location.txt", ["location"]),
        ("06_flooring.json", ["timeline"]),
        ("08_door_no_contact.json", ["contact"]),
        ("09_vague_messy.txt", ["project_type", "timeline", "budget_hint"]),
    ],
)
def test_missing_is_explicit(filename, expected):
    lead = rule_extract(Inquiry.from_path(SAMPLES / filename))
    assert lead.missing == expected
    for key in expected:
        if key != "contact":
            assert getattr(lead, key) is None


@pytest.mark.parametrize("filename", ["03_deck_messy.txt", "07_basement_messy.txt"])
def test_messy_inquiries(filename):
    lead = rule_extract(Inquiry.from_path(SAMPLES / filename))
    assert not lead.missing
    assert lead.email or lead.phone


@pytest.mark.parametrize("placeholder", ["unknown", "TBD", "not sure", "N/A", "undecided", "?"])
def test_unknown_labels_stay_missing(placeholder):
    inquiry = Inquiry("email.txt", f"Location: {placeholder}\nBudget: {placeholder}")
    lead = rule_extract(inquiry)
    assert lead.location is None
    assert lead.budget_hint is None
    assert "contact" in lead.missing


def test_no_location_inferred_from_phone_or_email():
    lead = rule_extract(Inquiry("x.txt", "nyc@example.com or +1 212-555-0100; door repair"))
    assert lead.phone == "+1 212-555-0100"
    assert lead.location is None


def test_literal_span():
    assert literal_span("custom shelves", "CUSTOM\n shelves") == "CUSTOM\n shelves"
    assert literal_span("New York", "Location: Fox Hollow, PA") is None
    assert literal_span("TBD", "TBD") is None


def test_blank_label_does_not_consume_next_field():
    lead = rule_extract(Inquiry("x", "Location: \nTimeline: next month\nBudget:\nName: Sam"))
    assert lead.location is None
    assert lead.budget_hint is None
    assert lead.timeline == "next month"
    assert lead.name == "Sam"


def mock_extractor(content, status=200):
    def handler(request):
        assert str(request.url) == f"{DEFAULT_BASE_URL}/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == DEFAULT_MODEL
        assert body["chat_template_kwargs"] == {"enable_thinking": False}
        assert body["messages"][0]["role"] == "system"
        return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})

    return Extractor(
        api_key="fictional-test-only", client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_llm_rejects_invented_values_and_invalid_contact():
    values = dict.fromkeys(FIELDS)
    values.update(
        email="email", project_type="door repair", location="Imaginary City", budget_hint="$20,000"
    )
    lead = mock_extractor(json.dumps(values)).extract(Inquiry("x", "email: door repair please"))
    assert lead.extractor == "llm"
    assert lead.project_type == "door repair"
    assert lead.location is None
    assert lead.budget_hint is None
    assert lead.email is None
    assert len(lead.warnings) == 3
    assert lead.evidence == {"project_type": "door repair"}


def test_llm_form_overrides_unsupported_guess():
    inquiry = Inquiry.from_path(SAMPLES / "02_bookshelves.json")
    values = dict.fromkeys(FIELDS)
    values.update(location="Made Up", project_type="deck replacement")
    lead = mock_extractor(json.dumps(values)).extract(inquiry)
    assert lead.location == "Maple Crossing, WA"
    assert lead.project_type == "custom bookshelves"
    assert not lead.missing


@pytest.mark.parametrize(
    ("content", "status"),
    [
        ("not JSON", 200),
        ("[]", 200),
        ("{}", 200),
        (json.dumps(dict.fromkeys(FIELDS, 42)), 200),
        ("{}", 401),
        ("{}", 429),
        ("{}", 503),
    ],
)
def test_bad_llm_response_falls_back_without_exposing_secrets(content, status):
    lead = mock_extractor(content, status).extract(Inquiry.from_path(SAMPLES / "01_kitchen.txt"))
    assert lead.extractor == "rules-fallback"
    assert not lead.missing
    assert "fictional-test-only" not in str(lead)


def test_timeout_falls_back():
    def handler(request):
        raise httpx.ReadTimeout("not logged", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    lead = Extractor(api_key="fictional-test-only", client=client).extract(
        Inquiry("x", "carpentry")
    )
    assert lead.extractor == "rules-fallback"


def test_rules_only_never_calls_network(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fictional-test-only")

    def fail(*args, **kwargs):
        pytest.fail("offline mode attempted HTTP")

    monkeypatch.setattr(httpx.Client, "post", fail)
    assert (
        Extractor.from_env(rules_only=True).extract(Inquiry("x", "door repair")).extractor
        == "rules"
    )


def test_contact_requirement_is_email_or_phone():
    assert "contact" in Lead(name="Avery").missing
    assert "contact" not in Lead(phone="202-555-0100").missing


def test_other_models_do_not_receive_nebius_specific_options():
    def handler(request):
        assert "chat_template_kwargs" not in json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(dict.fromkeys(FIELDS)),
                        },
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    lead = Extractor(api_key="fictional-test-only", model="another-model", client=client).extract(
        Inquiry("x", "Can you help?")
    )
    assert lead.extractor == "llm"


def test_truncated_response_is_rejected_even_if_json_parses():
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "finish_reason": "length",
                            "message": {
                                "content": json.dumps(dict.fromkeys(FIELDS)),
                            },
                        }
                    ],
                },
            )
        )
    )
    lead = Extractor(api_key="fictional-test-only", client=client).extract(
        Inquiry("x", "carpentry")
    )
    assert lead.extractor == "rules-fallback"


@pytest.mark.parametrize("envelope", [{}, {"choices": []}, {"choices": [None]}, {"choices": [42]}])
def test_malformed_completion_envelope_falls_back(envelope):
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=envelope))
    )
    lead = Extractor(api_key="fictional-test-only", client=client).extract(
        Inquiry("x", "carpentry")
    )
    assert lead.extractor == "rules-fallback"
