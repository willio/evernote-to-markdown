# Contributing to enex2writer

Thanks for helping improve `enex2writer`.

## Development setup

Python 3.10 or newer is supported. A local editable install is optional:

```sh
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
```

The project has no runtime dependencies. Tests build temporary ENEX fixtures
and never use a real Evernote export.

## Pull requests

- Keep the converter offline and dependency-free at runtime.
- Add or update tests for behavior changes.
- Do not commit real ENEX exports, note content, attachments, credentials, or
  other private data.
- Keep filenames and generated links safe on macOS, Linux, and Windows.
- Describe compatibility or migration trade-offs in the pull request.

Before opening a pull request, run:

```sh
python3 -m unittest discover -s tests -v
python3 -m pip wheel . --no-deps --no-build-isolation --wheel-dir /tmp/enex2writer-wheel
```

## Scope

The project focuses on a reliable local ENEX-to-Markdown migration. OCR,
Evernote API synchronization, decryption of encrypted notes, and network
services are intentionally outside the current scope.
