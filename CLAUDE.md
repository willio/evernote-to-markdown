# Maintainer notes

## Commands

```sh
python3 -m unittest discover -s tests -v
python3 -m pip wheel . --no-deps --no-build-isolation --wheel-dir /tmp/enex2writer-wheel
```

Run the CLI after installing the package, or use `PYTHONPATH=src` during local
development:

```sh
PYTHONPATH=src python3 -m enex2writer INPUT.enex OUTPUT_DIR --dry-run
```

## Architecture

- `src/enex2writer/enex.py` parses ENEX and decodes resources.
- `src/enex2writer/markdown.py` renders ENML/HTML fragments without third-party
  packages.
- `src/enex2writer/converter.py` plans filenames, links, assets, and writes the
  output plus manifest.
- `tests/test_converter.py` covers metadata, formatting, attachments, links,
  dry runs, overwrite protection, and optional output files.

Preserve the offline runtime boundary and never add real exports or private
data to fixtures.
