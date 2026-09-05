"""Streaming, local-only parsing of Evernote ENEX files."""

from __future__ import annotations

import base64
import binascii
from pathlib import Path
import re
from typing import Iterator
import xml.etree.ElementTree as ET

from .models import Note, Resource


def _local_name(tag: str) -> str:
    """Return an XML tag name without an optional namespace."""

    return tag.rsplit("}", 1)[-1]


def _direct_child(element: ET.Element, name: str) -> ET.Element | None:
    wanted = name.casefold()
    for child in list(element):
        if _local_name(child.tag).casefold() == wanted:
            return child
    return None


def _text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def _normalise_guid(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    cleaned = re.sub(r"^(?:urn:uuid:|evernote:)+", "", cleaned, flags=re.I)
    return cleaned.strip() or None


def _note_guid(note_element: ET.Element, attributes: dict[str, str]) -> str | None:
    candidate_names = {"note-guid", "note-id", "guid"}
    for child in list(note_element):
        if _local_name(child.tag).casefold() in candidate_names:
            result = _normalise_guid(_text(child))
            if result:
                return result
    for name, value in attributes.items():
        if name.casefold() in candidate_names:
            result = _normalise_guid(value)
            if result:
                return result
    return None


def _decode_resource(data_text: str, note_index: int, resource_index: int, warnings: list[str]) -> bytes | None:
    encoded = re.sub(r"\s+", "", data_text).encode("ascii", errors="ignore")
    if not encoded:
        return b""
    encoded += b"=" * (-len(encoded) % 4)
    try:
        return base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        warnings.append(
            f"Note {note_index}, resource {resource_index}: invalid base64 data ({error}); resource skipped."
        )
        return None


def _parse_resource(
    resource_element: ET.Element,
    note_index: int,
    resource_index: int,
    warnings: list[str],
) -> Resource | None:
    data_element = _direct_child(resource_element, "data")
    data_text = _text(data_element)
    encoding = (data_element.get("encoding", "base64") if data_element is not None else "base64").casefold()
    if encoding not in {"base64", ""}:
        warnings.append(
            f"Note {note_index}, resource {resource_index}: unsupported encoding {encoding!r}; resource skipped."
        )
        return None

    data = _decode_resource(data_text, note_index, resource_index, warnings)
    if data is None:
        return None

    resource_attributes_element = _direct_child(resource_element, "resource-attributes")
    resource_attributes: dict[str, str] = {}
    if resource_attributes_element is not None:
        for child in list(resource_attributes_element):
            value = _text(child)
            if value:
                resource_attributes[_local_name(child.tag).casefold()] = value

    mime = _text(_direct_child(resource_element, "mime"))
    filename = resource_attributes.get("file-name") or resource_attributes.get("filename")
    resource_id = _text(_direct_child(resource_element, "resource-id")) or resource_attributes.get("resource-id")
    hash_value = _text(_direct_child(resource_element, "hash")) or resource_attributes.get("hash")

    return Resource(
        index=resource_index,
        data=data,
        mime=mime,
        filename=filename,
        resource_id=resource_id,
        hash_value=hash_value,
    )


def _parse_note(note_element: ET.Element, note_index: int, warnings: list[str]) -> Note:
    attributes_element = _direct_child(note_element, "note-attributes")
    attributes: dict[str, str] = {}
    if attributes_element is not None:
        for child in list(attributes_element):
            value = _text(child)
            if value:
                attributes[_local_name(child.tag)] = value

    title = _text(_direct_child(note_element, "title")) or "Untitled note"
    content = _text(_direct_child(note_element, "content"))
    tags = [_text(child) for child in list(note_element) if _local_name(child.tag).casefold() == "tag"]
    tags = [tag for tag in tags if tag]

    resources: list[Resource] = []
    for resource_index, child in enumerate(
        (child for child in list(note_element) if _local_name(child.tag).casefold() == "resource"),
        start=1,
    ):
        resource = _parse_resource(child, note_index, resource_index, warnings)
        if resource is not None:
            resources.append(resource)

    return Note(
        index=note_index,
        title=title,
        content=content,
        created=_text(_direct_child(note_element, "created")) or None,
        updated=_text(_direct_child(note_element, "updated")) or None,
        tags=tags,
        attributes=attributes,
        guid=_note_guid(note_element, attributes),
        resources=resources,
    )


def parse_enex(path: Path) -> tuple[list[Note], list[str]]:
    """Parse an ENEX file and return notes plus non-fatal warnings.

    ``iterparse`` keeps the whole export out of memory at once in the common
    case of a large notebook. ElementTree does not fetch the ENML doctype or
    any external URL; the nested ENML body is treated as text and parsed later
    as a local HTML fragment.
    """

    notes: list[Note] = []
    warnings: list[str] = []
    try:
        events = ET.iterparse(path, events=("end",))
        for _event, element in events:
            if _local_name(element.tag).casefold() != "note":
                continue
            notes.append(_parse_note(element, len(notes) + 1, warnings))
            element.clear()
    except (ET.ParseError, OSError) as error:
        raise ValueError(f"could not parse ENEX file {path}: {error}") from error
    return notes, warnings


def iter_notes(path: Path) -> Iterator[Note]:
    """Yield parsed notes for callers that want an iterator-shaped interface."""

    notes, _warnings = parse_enex(path)
    yield from notes
