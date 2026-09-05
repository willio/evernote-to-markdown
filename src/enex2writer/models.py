"""Small data models used by the ENEX conversion pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib


@dataclass(slots=True)
class Resource:
    """A binary Evernote resource extracted from a note."""

    index: int
    data: bytes
    mime: str = ""
    filename: str | None = None
    resource_id: str | None = None
    hash_value: str | None = None

    @property
    def digest(self) -> str:
        """Return a stable digest used for asset de-duplication."""

        return hashlib.sha256(self.data).hexdigest()


@dataclass(slots=True)
class Note:
    """The note-level data needed to render a Markdown file."""

    index: int
    title: str
    content: str
    created: str | None = None
    updated: str | None = None
    tags: list[str] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)
    guid: str | None = None
    resources: list[Resource] = field(default_factory=list)
