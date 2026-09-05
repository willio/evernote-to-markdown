# enex2writer

Offline Evernote ENEX → Markdown conversion for iA Writer and other
Markdown-first editors.

`enex2writer` turns an Evernote desktop ENEX export into one UTF-8 `.md` file
per note, a shared `assets/` directory, and a `manifest.json` conversion
report. It uses only Python’s standard library at runtime, so the conversion
can run without network access.

## Features

- Preserves note titles, body text, headings, paragraphs, emphasis, lists,
  checkboxes, blockquotes, tables, code blocks, and horizontal rules.
- Extracts images and other ENEX resources, linking attachments from Markdown.
- Writes created/updated timestamps and tags in YAML frontmatter.
- Rewrites common Evernote internal links to local Markdown when the target is
  present in the same export.
- Preserves unresolved Evernote links and reports them in `manifest.json`.
- Uses safe filenames, resolves duplicate titles, deduplicates identical
  resources, and refuses accidental note overwrites by default.
- Makes no HTTP/API calls and does not perform OCR on scanned documents.

## Requirements and installation

Python 3.10 or newer is required. Install from a checkout:

```sh
python3 -m pip install .
```

For development, an editable install is convenient:

```sh
python3 -m pip install -e .
```

The package has no runtime dependencies. Building the wheel may use the
standard setuptools build backend declared in `pyproject.toml`.

## Quick start

1. In Evernote Desktop, export a notebook as ENEX with tags and attributes.
2. Convert it into a new folder:

```sh
enex2writer ~/Exports/Research.enex ~/Documents/Notes/Research
```

The same command is available as a module:

```sh
python3 -m enex2writer ~/Exports/Research.enex ~/Documents/Notes/Research
```

Preview the counts without writing anything:

```sh
enex2writer Research.enex Notes/Research --dry-run
```

If the destination already contains a note with the same planned filename,
the command stops safely. Use `--overwrite` only when replacing those files is
intentional:

```sh
enex2writer Research.enex Notes/Research --overwrite
```

The converter never deletes unrelated files in the destination.

## Output layout

```text
Research/
├── A useful note.md
├── Another note.md
├── assets/
│   ├── diagram.png
│   └── paper.pdf
└── manifest.json
```

Example note:

```markdown
---
title: "A useful note"
created: "2024-03-12T09:30:00Z"
updated: "2026-07-01T14:05:00Z"
tags:
  - "work"
  - "idea"
source: "evernote"
evernote_guid: "0123456789abcdef0123456789abcdef"
---

# A useful note

The converted note body appears here.
```

Relative Markdown links use the generated filenames, and attachment links
point into `assets/`. The manifest contains the source filename, note-to-file
mapping, extracted resources, warnings, and unresolved internal links.

## Command reference

```text
enex2writer INPUT.enex OUTPUT_DIR [options]

Options:
  --overwrite       Replace existing generated note/asset/manifest files.
  --no-manifest     Do not write manifest.json.
  --no-frontmatter  Omit YAML frontmatter from generated notes.
  --dry-run         Parse and plan the conversion without writing files.
  -q, --quiet       Print only errors.
  -V, --version     Print the installed version.
  -h, --help        Show help.
```

## What to inspect after migration

Run a small notebook first, then review images, PDFs, checkboxes, tables,
encrypted notes, clipped web pages, and internal links in iA Writer. Evernote
encrypted content is preserved only to the extent that it is present in the
ENEX export; this tool does not decrypt it. Scanned PDFs are copied as files,
but OCR is outside the project’s scope.

## Development

Run the standard-library test suite from the project root:

```sh
python3 -m unittest discover -s tests -v
```

The project is released under the MIT License. See [`LICENSE`](LICENSE).

For contribution expectations, see [`CONTRIBUTING.md`](CONTRIBUTING.md). The
release-readiness record is [`docs/oss-checklist.md`](docs/oss-checklist.md),
and vulnerability-reporting guidance is in [`SECURITY.md`](SECURITY.md).
