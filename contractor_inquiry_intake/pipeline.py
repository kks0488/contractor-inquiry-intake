"""Process a batch, dedupe before LLM calls, and notify the owner once."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx

from .extract import Extractor
from .models import FIELDS, Inquiry, Lead
from .storage import CSVStore, SheetsSink


@dataclass
class Result:
    source: str
    inquiry_id: str
    status: str
    lead: Lead | None = None


@dataclass
class Batch:
    results: list[Result] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def added(self) -> int:
        return sum(result.status == "ADDED" for result in self.results)

    @property
    def duplicates(self) -> int:
        return sum(result.status == "DUPLICATE" for result in self.results)

    @property
    def errors(self) -> int:
        return sum(result.status == "ERROR" for result in self.results)

    def summary(self) -> str:
        lines = [
            f"Contractor intake: {self.added} new, "
            f"{self.duplicates} duplicate, {self.errors} error."
        ]
        for result in self.results:
            if result.lead:
                lead = result.lead
                lines.append(
                    f"{lead.name or 'Unnamed'} | {lead.email or lead.phone or 'MISSING contact'} | "
                    f"{lead.project_type or 'MISSING project'} | "
                    f"{lead.location or 'MISSING location'} | "
                    f"timeline: {lead.timeline or 'MISSING'} | "
                    f"budget: {lead.budget_hint or 'MISSING'}"
                    f" | MISSING: {', '.join(lead.missing) or 'none'}"
                )
        lines.extend(self.warnings)
        return "\n".join(lines)

    def markdown(self) -> str:
        columns = (
            "Source",
            "Status",
            "Contact",
            "Project",
            "Location",
            "Timeline",
            "Budget hint",
            "MISSING",
            "Extractor",
        )
        lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * 9) + " |"]
        for result in self.results:
            lead = result.lead
            cells = [result.source, result.status]
            if lead:
                contact = " / ".join(
                    value for value in (lead.name, lead.email, lead.phone) if value
                )
                cells += [
                    contact or "MISSING",
                    lead.project_type or "MISSING",
                    lead.location or "MISSING",
                    lead.timeline or "MISSING",
                    lead.budget_hint or "MISSING",
                    ", ".join(lead.missing) or "—",
                    lead.extractor,
                ]
            else:
                cells += ["—"] * 7
            lines.append(
                "| "
                + " | ".join(
                    html.escape(cell).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
                    for cell in cells
                )
                + " |"
            )
        return "\n".join(lines)


def to_row(inquiry: Inquiry, lead: Lead) -> dict[str, str]:
    return {
        "inquiry_id": inquiry.inquiry_id,
        "source": inquiry.source,
        **{key: getattr(lead, key) or "" for key in FIELDS},
        "missing": ", ".join(lead.missing),
        "extractor": lead.extractor,
        "evidence": json.dumps(lead.evidence, ensure_ascii=False, sort_keys=True),
        "warnings": "; ".join(lead.warnings),
        "received_at": datetime.now(UTC).isoformat(),
    }


def run(
    paths: list[Path], store: CSVStore, extractor: Extractor, sheets: SheetsSink | None = None
) -> Batch:
    batch = Batch()
    seen = store.ids()
    rows = []
    for path in paths:
        try:
            inquiry = Inquiry.from_path(path)
            if not inquiry.text.strip():
                raise ValueError("empty input")
        except (OSError, UnicodeError, ValueError):
            batch.results.append(Result(path.name, "", "ERROR"))
            batch.warnings.append(f"{path.name}: could not read a valid inquiry")
            continue
        if inquiry.inquiry_id in seen:
            batch.results.append(Result(path.name, inquiry.inquiry_id, "DUPLICATE"))
            continue
        lead = extractor.extract(inquiry)
        row = to_row(inquiry, lead)
        if store.append(row):
            rows.append(row)
            batch.results.append(Result(path.name, inquiry.inquiry_id, "ADDED", lead))
        else:
            batch.results.append(Result(path.name, inquiry.inquiry_id, "DUPLICATE"))
        seen.add(inquiry.inquiry_id)
    if sheets and rows:
        try:
            sheets.append(rows)
        except Exception:
            # Authentication/network/library errors must not discard captured leads.
            batch.warnings.append("Sheets append failed; all new rows remain in local CSV")
    return batch


def notify_slack(summary: str, webhook_url: str, *, client: httpx.Client | None = None) -> bool:
    # plain_text prevents customer-controlled Slack markup and mentions.
    payload = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": summary[:2900],
                },
            }
        ]
    }
    try:
        if client is not None:
            response = client.post(webhook_url, json=payload, timeout=15)
        else:
            with httpx.Client(follow_redirects=False) as session:
                response = session.post(webhook_url, json=payload, timeout=15)
        response.raise_for_status()
        return response.text.strip() == "ok"
    except (httpx.HTTPError, ValueError):
        return False
