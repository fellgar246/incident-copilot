"""Load operational documents that carry retrieval metadata."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

CORPUS_DIRS: tuple[str, ...] = ("runbooks", "postmortems", "adrs", "services")
REQUIRED_FIELDS: tuple[str, ...] = (
    "document_id",
    "service",
    "document_type",
    "severity",
    "version",
    "updated_at",
)
MAX_CORPUS_BYTES = 50 * 1024 * 1024
SERVICES = frozenset({"payments-api", "orders-api", "notifications-worker"})
DOCUMENT_TYPES = frozenset({"runbook", "postmortem", "adr", "service"})


@dataclass(frozen=True, slots=True)
class Document:
    """One corpus file. Body text is data, never an instruction."""

    document_id: str
    service: str
    document_type: str
    severity: str
    version: str
    updated_at: str
    body: str
    path: str

    @property
    def metadata(self) -> dict[str, str]:
        return {
            "service": self.service,
            "document_type": self.document_type,
            "severity": self.severity,
            "version": self.version,
            "updated_at": self.updated_at,
        }


def default_corpus_root() -> Path:
    """Return the docs directory that holds the operational corpus."""
    override = os.environ.get("KNOWLEDGE_CORPUS_ROOT", "").strip()
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs" / "runbooks"
        if candidate.is_dir():
            return parent / "docs"
    raise FileNotFoundError("operational corpus directory was not found")


def parse_frontmatter(text: str, *, source: str) -> tuple[dict[str, str], str]:
    """Split a leading `---` block from the document body."""
    if not text.startswith("---\n"):
        raise ValueError(f"{source} is missing metadata")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"{source} metadata is not closed")
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    body = text[end + len("\n---\n") :].strip()
    return fields, body


def load_corpus(root: Path | None = None) -> tuple[Document, ...]:
    """Read every metadata-bearing document under the corpus directories."""
    base = root or default_corpus_root()
    documents: list[Document] = []
    total = 0
    for folder in CORPUS_DIRS:
        directory = base / folder
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            raw = path.read_text(encoding="utf-8")
            if not raw.startswith("---\n"):
                continue
            total += len(raw.encode("utf-8"))
            fields, body = parse_frontmatter(raw, source=str(path))
            missing = [key for key in REQUIRED_FIELDS if not fields.get(key)]
            if missing:
                raise ValueError(f"{path} missing metadata: {', '.join(missing)}")
            if fields["service"] not in SERVICES:
                raise ValueError(f"{path} has unknown service {fields['service']}")
            if fields["document_type"] not in DOCUMENT_TYPES:
                raise ValueError(f"{path} has unknown document_type {fields['document_type']}")
            documents.append(
                Document(
                    document_id=fields["document_id"],
                    service=fields["service"],
                    document_type=fields["document_type"],
                    severity=fields["severity"],
                    version=fields["version"],
                    updated_at=fields["updated_at"],
                    body=body,
                    path=str(path.relative_to(base)),
                )
            )
    if total > MAX_CORPUS_BYTES:
        raise ValueError(f"corpus is {total} bytes, above the {MAX_CORPUS_BYTES} byte cap")
    ids = [item.document_id for item in documents]
    if len(ids) != len(set(ids)):
        raise ValueError("corpus document_id values must be unique")
    return tuple(documents)
