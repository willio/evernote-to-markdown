"""High-level ENEX to Markdown conversion orchestration."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import mimetypes
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote, unquote

from .enex import parse_enex
from .filenames import safe_component, unique_filename, with_numeric_suffix
from .markdown import AssetReference, MarkdownRenderer
from .models import Note, Resource
from .version import __version__


class ConversionError(RuntimeError):
    """A user-actionable conversion or destination error."""


@dataclass(slots=True)
class ConversionResult:
    """Summary returned by :func:`convert`."""

    output_dir: Path
    note_count: int
    asset_count: int
    manifest_written: bool
    warnings: list[str]
    unresolved_internal_links: list[dict[str, str]]
    dry_run: bool = False


@dataclass(slots=True)
class _PlannedNote:
    note: Note
    filename: str


@dataclass(slots=True)
class _AssetEntry:
    reference: AssetReference
    data: bytes
    digest: str
    mime: str
    original_name: str | None


_MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}
_IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".tif", ".tiff", ".webp"}
_GUID_PATTERN = re.compile(
    r"(?i)(?:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|[0-9a-f]{32})"
)
_TIMESTAMP_PATTERN = re.compile(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(\d*)Z$", re.I)


def _alias_keys(value: str | None) -> list[str]:
    if not value:
        return []
    raw = unquote(str(value)).strip().casefold()
    if not raw:
        return []
    result = [raw]
    compact = re.sub(r"[^0-9a-z]", "", raw)
    if compact and compact not in result:
        result.append(compact)
    return result


def _guid_keys(value: str | None) -> list[str]:
    result: list[str] = []
    for key in _alias_keys(value):
        if key not in result:
            result.append(key)
    if value:
        for match in _GUID_PATTERN.findall(unquote(str(value))):
            for key in _alias_keys(match):
                if key not in result:
                    result.append(key)
    return result


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resource_basename(filename: str | None) -> str | None:
    if not filename:
        return None
    return re.split(r"[/\\]", filename.strip())[-1] or None


class _AssetCatalog:
    """Plan and write shared, deduplicated resources."""

    def __init__(self, output_dir: Path, *, overwrite: bool) -> None:
        self.output_dir = output_dir
        self.overwrite = overwrite
        self._by_digest: dict[str, _AssetEntry] = {}
        self._by_alias: dict[str, AssetReference] = {}
        self._used_names: set[str] = set()
        self.entries: list[_AssetEntry] = []

    def register(self, resource: Resource) -> AssetReference:
        digest = resource.digest
        existing = self._by_digest.get(digest)
        if existing is not None:
            self._register_aliases(resource, existing.reference)
            return existing.reference

        original_name = _resource_basename(resource.filename)
        fallback = f"attachment-{resource.index}"
        candidate = safe_component(original_name, fallback, max_length=180)
        mime = resource.mime.split(";", 1)[0].strip().casefold()
        if "." not in candidate.rsplit("/", 1)[-1]:
            extension = _MIME_EXTENSIONS.get(mime) or mimetypes.guess_extension(mime) or ""
            candidate = f"{candidate}{extension}"

        number = 2
        while True:
            key = candidate.casefold()
            path = self.output_dir / "assets" / candidate
            if key in self._used_names:
                candidate = with_numeric_suffix(candidate, number)
                number += 1
                continue
            if path.exists() and not self.overwrite:
                if path.is_file() and _sha256_file(path) == digest:
                    reference = AssetReference(f"assets/{candidate}", candidate, self._is_image(mime, candidate))
                    entry = _AssetEntry(reference, resource.data, digest, resource.mime, original_name)
                    self._by_digest[digest] = entry
                    self._used_names.add(key)
                    self._register_aliases(resource, reference)
                    self.entries.append(entry)
                    return reference
                candidate = with_numeric_suffix(candidate, number)
                number += 1
                continue
            break

        self._used_names.add(key)
        reference = AssetReference(f"assets/{candidate}", candidate, self._is_image(mime, candidate))
        entry = _AssetEntry(reference, resource.data, digest, resource.mime, original_name)
        self._by_digest[digest] = entry
        self._register_aliases(resource, reference)
        self.entries.append(entry)
        return reference

    @staticmethod
    def _is_image(mime: str, filename: str) -> bool:
        return mime.startswith("image/") or Path(filename).suffix.casefold() in _IMAGE_EXTENSIONS

    def _register_aliases(self, resource: Resource, reference: AssetReference) -> None:
        aliases = [resource.hash_value, resource.resource_id, resource.digest, resource.filename]
        for alias in aliases:
            for key in _alias_keys(alias):
                self._by_alias.setdefault(key, reference)

    def resolve(self, attrs: dict[str, str]) -> AssetReference | None:
        for name in ("hash", "resource-id", "resource_id", "id", "file-name", "filename"):
            for key in _alias_keys(attrs.get(name)):
                reference = self._by_alias.get(key)
                if reference is not None:
                    return reference
        return None

    def write(self) -> int:
        if not self.entries:
            return 0
        assets_dir = self.output_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        written = 0
        for entry in self.entries:
            path = self.output_dir / entry.reference.relative_path
            if path.exists():
                if path.is_file() and _sha256_file(path) == entry.digest:
                    continue
                if not self.overwrite:
                    raise ConversionError(f"refusing to overwrite existing asset: {path}")
            path.write_bytes(entry.data)
            written += 1
        return written


class _NoteLinkResolver:
    """Resolve exported-note GUIDs and exact title labels to local files."""

    def __init__(self, planned_notes: list[_PlannedNote]) -> None:
        self._by_guid: dict[str, str] = {}
        self._by_title: dict[str, str] = {}
        self.unresolved: list[dict[str, str]] = []
        self._unresolved_keys: set[tuple[str, str, str]] = set()
        for planned in planned_notes:
            for key in _guid_keys(planned.note.guid):
                self._by_guid.setdefault(key, planned.filename)
            title_key = self._title_key(planned.note.title)
            if title_key:
                self._by_title.setdefault(title_key, planned.filename)

    @staticmethod
    def _title_key(value: str) -> str:
        value = re.sub(r"[*_~`]", "", value)
        return re.sub(r"\s+", " ", value).strip().casefold()

    def resolve(self, href: str, label: str, source_filename: str) -> str:
        if not href.casefold().startswith("evernote:"):
            return href

        target: str | None = None
        for key in _guid_keys(href):
            target = self._by_guid.get(key)
            if target is not None:
                break
        if target is None:
            target = self._by_title.get(self._title_key(label))
        if target is not None:
            return quote(target, safe="-._~")

        key = (source_filename, href, label)
        if key not in self._unresolved_keys:
            self._unresolved_keys.add(key)
            self.unresolved.append({"from": source_filename, "label": label, "href": href})
        return href


def normalize_timestamp(value: str | None) -> str | None:
    """Convert Evernote's compact UTC timestamp to an ISO-8601 value."""

    if not value:
        return None
    raw = value.strip()
    match = _TIMESTAMP_PATTERN.match(raw)
    if not match:
        return raw or None
    year, month, day, hour, minute, second, fraction = match.groups()
    if fraction:
        fraction = (fraction + "000000")[:6]
        return f"{year}-{month}-{day}T{hour}:{minute}:{second}.{fraction}Z"
    return f"{year}-{month}-{day}T{hour}:{minute}:{second}Z"


def _yaml_scalar(value: str) -> str:
    # JSON strings are valid YAML scalars and handle quotes/newlines safely.
    return json.dumps(value, ensure_ascii=False)


def _frontmatter(note: Note) -> str:
    lines = ["---", f"title: {_yaml_scalar(note.title)}"]
    created = normalize_timestamp(note.created)
    updated = normalize_timestamp(note.updated)
    if created:
        lines.append(f"created: {_yaml_scalar(created)}")
    if updated:
        lines.append(f"updated: {_yaml_scalar(updated)}")
    if note.tags:
        lines.append("tags:")
        lines.extend(f"  - {_yaml_scalar(tag)}" for tag in note.tags)
    else:
        lines.append("tags: []")
    lines.append('source: "evernote"')
    if note.guid:
        lines.append(f"evernote_guid: {_yaml_scalar(note.guid)}")
    if note.attributes:
        attributes = json.dumps(note.attributes, ensure_ascii=False, sort_keys=True)
        lines.append(f"evernote_attributes: {attributes}")
    lines.append("---")
    return "\n".join(lines)


def _note_markdown(note: Note, body: str, *, include_frontmatter: bool) -> str:
    title = re.sub(r"\s+", " ", note.title.replace("\r", " ").replace("\n", " ")).strip()
    title = title or "Untitled note"
    parts = [_frontmatter(note)] if include_frontmatter else []
    parts.append(f"# {title}")
    if body.strip():
        parts.append(body.strip())
    return "\n\n".join(parts) + "\n"


def _manifest(
    input_path: Path,
    planned_notes: list[_PlannedNote],
    catalog: _AssetCatalog,
    warnings: list[str],
    unresolved: list[dict[str, str]],
) -> dict[str, Any]:
    notes: list[dict[str, Any]] = []
    for planned in planned_notes:
        resource_entries: list[dict[str, Any]] = []
        for resource in planned.note.resources:
            reference = catalog._by_digest.get(resource.digest)
            resource_entries.append(
                {
                    "original_name": resource.filename,
                    "mime": resource.mime or None,
                    "sha256": resource.digest,
                    "file": reference.reference.relative_path if reference else None,
                }
            )
        notes.append(
            {
                "title": planned.note.title,
                "file": planned.filename,
                "created": normalize_timestamp(planned.note.created),
                "updated": normalize_timestamp(planned.note.updated),
                "tags": planned.note.tags,
                "evernote_guid": planned.note.guid,
                "resources": resource_entries,
            }
        )
    return {
        "format": "enex2writer-manifest-v1",
        "converter_version": __version__,
        "source": input_path.name,
        "notes": notes,
        "unresolved_internal_links": unresolved,
        "warnings": warnings,
    }


def _preflight(
    output_dir: Path,
    planned_notes: list[_PlannedNote],
    *,
    overwrite: bool,
    write_manifest: bool,
) -> None:
    if output_dir.exists() and not output_dir.is_dir():
        raise ConversionError(f"output path is not a directory: {output_dir}")
    if overwrite:
        return
    conflicts = [output_dir / planned.filename for planned in planned_notes if (output_dir / planned.filename).exists()]
    if write_manifest and (output_dir / "manifest.json").exists():
        conflicts.append(output_dir / "manifest.json")
    if conflicts:
        joined = ", ".join(str(path) for path in conflicts[:5])
        suffix = "" if len(conflicts) <= 5 else f" (and {len(conflicts) - 5} more)"
        raise ConversionError(
            f"refusing to overwrite existing generated file(s): {joined}{suffix}; use --overwrite if intentional"
        )


def convert(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
    write_manifest: bool = True,
    include_frontmatter: bool = True,
    dry_run: bool = False,
) -> ConversionResult:
    """Convert an ENEX export into Markdown and return a conversion summary."""

    source = Path(input_path).expanduser()
    destination = Path(output_dir).expanduser()
    if not source.is_file():
        raise ConversionError(f"input ENEX file does not exist: {source}")

    try:
        notes, warnings = parse_enex(source)
    except ValueError as error:
        raise ConversionError(str(error)) from error

    used_names: set[str] = set()
    planned_notes: list[_PlannedNote] = []
    for note in notes:
        stem = safe_component(note.title, f"Untitled note {note.index}")
        candidate = stem if stem.casefold().endswith(".md") else f"{stem}.md"
        planned_notes.append(_PlannedNote(note, unique_filename(candidate, used_names)))

    _preflight(destination, planned_notes, overwrite=overwrite, write_manifest=write_manifest)
    catalog = _AssetCatalog(destination, overwrite=overwrite)
    for note in notes:
        for resource in note.resources:
            catalog.register(resource)

    link_resolver = _NoteLinkResolver(planned_notes)
    rendered_notes: list[tuple[_PlannedNote, str]] = []
    for planned in planned_notes:
        def resolve_resource(attrs: dict[str, str], *, filename: str = planned.filename) -> AssetReference | None:
            reference = catalog.resolve(attrs)
            if reference is None:
                identifier = attrs.get("hash") or attrs.get("resource-id") or "unknown"
                warning = f"{filename}: missing ENML resource reference {identifier}"
                if warning not in warnings:
                    warnings.append(warning)
            return reference

        renderer = MarkdownRenderer(
            resource_resolver=resolve_resource,
            link_resolver=lambda href, label, filename=planned.filename: link_resolver.resolve(
                href, label, filename
            ),
        )
        body = renderer.render(planned.note.content)
        rendered_notes.append((planned, _note_markdown(planned.note, body, include_frontmatter=include_frontmatter)))

    if dry_run:
        return ConversionResult(
            output_dir=destination,
            note_count=len(planned_notes),
            asset_count=len(catalog.entries),
            manifest_written=False,
            warnings=warnings,
            unresolved_internal_links=link_resolver.unresolved,
            dry_run=True,
        )

    destination.mkdir(parents=True, exist_ok=True)
    assets_written = catalog.write()
    for planned, content in rendered_notes:
        (destination / planned.filename).write_text(content, encoding="utf-8", newline="\n")

    manifest_written = False
    if write_manifest:
        manifest = _manifest(source, planned_notes, catalog, warnings, link_resolver.unresolved)
        (destination / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        manifest_written = True

    return ConversionResult(
        output_dir=destination,
        note_count=len(planned_notes),
        asset_count=assets_written,
        manifest_written=manifest_written,
        warnings=warnings,
        unresolved_internal_links=link_resolver.unresolved,
    )


__all__ = ["ConversionError", "ConversionResult", "convert", "normalize_timestamp"]
