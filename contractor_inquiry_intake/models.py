"""Input contract and output schema; unknown information stays null."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

FIELDS = ("name", "email", "phone", "project_type", "location", "timeline", "budget_hint")
CSV_COLUMNS = (
    "inquiry_id",
    "source",
    *FIELDS,
    "missing",
    "extractor",
    "evidence",
    "warnings",
    "received_at",
)
UNKNOWN = re.compile(
    r"^(?:unknown|unspecified|not (?:sure|provided|specified|known|decided)|"
    r"tbd|tba|n/?a|none|null|undecided|to be (?:decided|confirmed)|[?—-]+)[.!?]*$",
    re.I,
)


def normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def known(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if value and not UNKNOWN.fullmatch(value) else None


@dataclass(frozen=True)
class Inquiry:
    source: str
    text: str
    form: dict[str, str] = field(default_factory=dict)

    @property
    def inquiry_id(self) -> str:
        # Content identity, independent of filename, extractor, or run date.
        return hashlib.sha256(normalize(self.text).encode()).hexdigest()

    @classmethod
    def from_path(cls, path: Path) -> Inquiry:
        raw = path.read_text(encoding="utf-8")
        if path.suffix.lower() != ".json":
            return cls(path.name, raw)
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("web form JSON must be one object")
        allowed = (*FIELDS, "message")
        form = {}
        for key in allowed:
            value = payload.get(key)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"web form field {key} must be a string or null")
            if isinstance(value, str) and value.strip():
                form[key] = value.strip()
        if not form:
            raise ValueError("web form has no supported nonempty fields")
        text = "\n".join(f"{key}: {form[key]}" for key in sorted(form))
        return cls(path.name, text, form)


@dataclass
class Lead:
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    project_type: str | None = None
    location: str | None = None
    timeline: str | None = None
    budget_hint: str | None = None
    extractor: str = "rules"
    evidence: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def missing(self) -> list[str]:
        required = ("project_type", "location", "timeline", "budget_hint")
        return (["contact"] if not (self.email or self.phone) else []) + [
            key for key in required if not getattr(self, key)
        ]
