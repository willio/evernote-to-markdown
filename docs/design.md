# Design notes

## Conversion pipeline

The command performs four local phases:

1. Parse the ENEX document into notes and resources.
2. Plan stable, filesystem-safe note names and deduplicated asset names.
3. Render ENML/HTML content to Markdown using a small standard-library parser.
4. Write notes, assets, and a JSON manifest after the plan is complete.

Planning before writing means malformed content is reported before most output
files are created, and collisions can be resolved without deleting anything.

## Metadata

Each note receives YAML frontmatter containing its original title, normalized
UTC timestamps, tags, source marker, and Evernote identifier when the export
contains one. The original title is also emitted as a Markdown H1 so the files
remain readable in editors that ignore frontmatter.

## Attachments

Resources are decoded from ENEX base64 data and placed in a shared `assets/`
directory. Resources with the same SHA-256 digest are written once. ENML
`en-media` elements are rendered as image embeds for image MIME types and as
ordinary links for other attachments. Missing resource references remain
visible in the Markdown and are listed in the manifest warnings.

## Internal links

Evernote links are rewritten when their GUID matches an exported note, or when
the link label exactly matches an exported note title. This handles the common
`evernote:///view/...` form without needing an online Evernote API. Links that
cannot be resolved are preserved verbatim and recorded in
`manifest.json` for follow-up.

## Safety and portability

The converter never deletes files and refuses to overwrite existing note files
unless `--overwrite` is supplied. Note and asset names are sanitized against
path traversal and common cross-platform filename restrictions. Runtime
dependencies are empty; the only network-related behavior is intentionally no
network behavior at all.
